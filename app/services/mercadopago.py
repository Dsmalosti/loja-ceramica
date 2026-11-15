"""Mercado Pago (Checkout Pro) sem SDK: duas chamadas HTTP com a urllib do Python.

Regras de segurança desta integração:
- O cliente paga na página do Mercado Pago. Número de cartão nunca passa pelo
  nosso servidor nem vai pro banco (fora do escopo pesado do PCI).
- Status e valor vêm SEMPRE da API do Mercado Pago (GET /v1/payments/<id>),
  autenticada com o nosso token. Nunca do corpo do webhook nem do ?status= da URL.
- O webhook confere a assinatura (HMAC-SHA256) antes de qualquer coisa.
- processar_pagamento() é idempotente: o mesmo aviso 2x não paga 2x.

Docs: developers.mercadopago.com (Checkout Pro > preferências; Notificações > Webhooks).
"""
import hashlib
import hmac
import json
import logging
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

from flask import current_app
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import EventoPagamento, Pedido, Product, agora
from ..utils import FUSO_BRASILIA
from .pedidos import registrar

log = logging.getLogger(__name__)

VALIDADE_PREFERENCIA = timedelta(hours=2)


class ErroMercadoPago(Exception):
    """Falha ao falar com o Mercado Pago (rede, timeout, resposta inesperada)."""


def configurado():
    cfg = current_app.config
    return bool(cfg.get("MP_ACCESS_TOKEN") and cfg.get("SITE_URL"))


def _requisicao(metodo, caminho, corpo=None, idempotencia=None):
    """Chamada autenticada à API. Os testes trocam esta função por um Mercado Pago falso."""
    cfg = current_app.config
    cabecalhos = {
        "Authorization": f"Bearer {cfg['MP_ACCESS_TOKEN']}",
        "Content-Type": "application/json",
    }
    if idempotencia:
        cabecalhos["X-Idempotency-Key"] = idempotencia
    dados = json.dumps(corpo).encode() if corpo is not None else None
    pedido = urllib.request.Request(cfg["MP_API_URL"] + caminho, data=dados, headers=cabecalhos, method=metodo)
    try:
        with urllib.request.urlopen(pedido, timeout=10) as resposta:
            return json.loads(resposta.read().decode())
    except urllib.error.HTTPError as erro:
        # Não loga o corpo inteiro nem cabeçalhos (o token vai no cabeçalho)
        raise ErroMercadoPago(f"HTTP {erro.code} em {metodo} {caminho}") from None
    except (urllib.error.URLError, TimeoutError, ValueError) as erro:
        raise ErroMercadoPago(f"{type(erro).__name__} em {metodo} {caminho}") from None


# ---------- Preferência (abre o pagamento) ----------

def criar_preferencia(pedido):
    """Cria a preferência do Checkout Pro e guarda id + link no pedido (não faz commit)."""
    site = current_app.config["SITE_URL"]
    itens = [
        {
            "id": str(item.produto_id),
            "title": item.nome_produto[:250],
            "quantity": item.quantidade,
            "unit_price": item.preco_unitario_centavos / 100,
            "currency_id": "BRL",
        }
        for item in pedido.itens
    ]
    if pedido.frete_centavos:
        itens.append({"id": "frete", "title": "Frete", "quantity": 1,
                      "unit_price": pedido.frete_centavos / 100, "currency_id": "BRL"})

    retorno = f"{site}/checkout/retorno/{pedido.id}"
    agora_br = datetime.now(FUSO_BRASILIA)
    corpo = {
        "items": itens,
        "external_reference": str(pedido.id),
        "payer": {"name": pedido.usuario.nome, "email": pedido.usuario.email},
        "back_urls": {"success": retorno, "pending": retorno, "failure": retorno},
        "auto_return": "approved",
        "notification_url": f"{site}/pagamento/webhook",
        "statement_descriptor": "JULIAMALOSTI",
        # Pix e cartão. Boleto fica de fora: leva dias e a peça é única.
        "payment_methods": {"excluded_payment_types": [{"id": "ticket"}]},
        "expires": True,
        "expiration_date_from": agora_br.isoformat(timespec="milliseconds"),
        "expiration_date_to": (agora_br + VALIDADE_PREFERENCIA).isoformat(timespec="milliseconds"),
    }
    resposta = _requisicao("POST", "/checkout/preferences", corpo, idempotencia=f"pedido-{pedido.id}")
    if not resposta.get("id") or not resposta.get("init_point"):
        raise ErroMercadoPago("preferência sem id/init_point")
    pedido.mp_preference_id = str(resposta["id"])
    pedido.mp_init_point = resposta["init_point"]
    return resposta


def consultar_pagamento(payment_id):
    return _requisicao("GET", f"/v1/payments/{payment_id}")


# ---------- Assinatura do webhook ----------

def assinatura_valida(x_signature, x_request_id, data_id, segredo):
    """Confere o cabeçalho x-signature ("ts=...,v1=...") do Mercado Pago.

    Manifesto: "id:<data.id>;request-id:<x-request-id>;ts:<ts>;" (par ausente é omitido),
    assinado com HMAC-SHA256 e a assinatura secreta da aplicação.
    """
    if not segredo or not x_signature:
        return False
    partes = dict(
        p.strip().split("=", 1) for p in x_signature.split(",") if "=" in p
    )
    ts, v1 = partes.get("ts"), partes.get("v1")
    if not ts or not v1:
        return False
    manifesto = ""
    if data_id:
        manifesto += f"id:{str(data_id).lower()};"
    if x_request_id:
        manifesto += f"request-id:{x_request_id};"
    manifesto += f"ts:{ts};"
    esperado = hmac.new(segredo.encode(), manifesto.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, v1)  # tempo constante: não vaza pelo relógio


# ---------- Processar um pagamento (webhook e volta do cliente) ----------

def _centavos(valor):
    try:
        return int((Decimal(str(valor)) * 100).quantize(Decimal("1")))
    except (InvalidOperation, TypeError, ValueError):
        return None


def processar_pagamento(payment_id):
    """Pergunta ao Mercado Pago e aplica o resultado no pedido. Idempotente.

    Devolve o pedido (ou None se o pagamento não é de um pedido nosso).
    Lança ErroMercadoPago se não conseguir consultar (quem chamou decide: o webhook
    responde 500 e o Mercado Pago reenvia).
    """
    dados = consultar_pagamento(payment_id)
    referencia = str(dados.get("external_reference") or "")
    status = str(dados.get("status") or "")
    if not referencia.isdigit() or not status:
        log.warning("Pagamento %s sem referência de pedido", payment_id)
        return None

    # Trava a linha do pedido até o commit (no Postgres): dois avisos ao mesmo tempo
    # não aprovam duas vezes. No SQLite o with_for_update é ignorado; o UNIQUE segura.
    pedido = db.session.get(Pedido, int(referencia), with_for_update=True)
    if pedido is None:
        log.warning("Pagamento %s aponta para pedido inexistente %s", payment_id, referencia)
        return None

    valor = _centavos(dados.get("transaction_amount"))
    if dados.get("currency_id") != "BRL" or valor != pedido.total_centavos:
        log.error("Pagamento %s com valor/moeda diferente do pedido %s", payment_id, pedido.id)
        db.session.rollback()
        return pedido

    db.session.add(EventoPagamento(pedido_id=pedido.id, mp_payment_id=str(payment_id),
                                   status=status, valor_centavos=valor))
    try:
        db.session.flush()
    except IntegrityError:
        # Esse (pagamento, status) já foi processado: não faz nada de novo
        db.session.rollback()
        return db.session.get(Pedido, int(referencia))

    if status == "approved" and pedido.status == "aguardando_pagamento":
        registrar(pedido, pedido.status, "pago", "mercado_pago")
        _aprovar(pedido, payment_id)
    elif status in ("cancelled", "expired") and pedido.status == "aguardando_pagamento":
        registrar(pedido, pedido.status, "cancelado", "mercado_pago")
        pedido.status = "cancelado"
    # rejected / pending / in_process: continua aguardando (dá pra tentar de novo)
    db.session.commit()
    return pedido


def _aprovar(pedido, payment_id):
    pedido.status = "pago"
    pedido.pago_em = agora()
    pedido.mp_payment_id = str(payment_id)
    for item in pedido.itens:
        # Baixa atômica: só se ainda houver estoque (nunca fica negativo)
        resultado = db.session.execute(
            update(Product)
            .where(Product.id == item.produto_id, Product.estoque >= item.quantidade)
            .values(estoque=Product.estoque - item.quantidade)
        )
        if resultado.rowcount == 0:
            pedido.estoque_insuficiente = True
            log.warning("Pedido %s pago sem estoque de %s", pedido.id, item.produto_id)
