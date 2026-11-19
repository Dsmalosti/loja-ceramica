"""Checkout Pro (Mercado Pago, sandbox): resumo, pedido, webhook e retorno.

Regras (skill saas-flask-seguranca, seção 8):
- nenhum dado de cartão passa pelo nosso servidor (o cliente paga na página do Mercado Pago);
- o webhook valida a assinatura e é idempotente (mesmo aviso 2x não paga 2x);
- valor e status vêm da API do Mercado Pago, nunca do navegador;
- o estoque só baixa com pagamento aprovado.

O Mercado Pago é simulado (MPFalso): nenhum teste sai pra internet.
"""
import hashlib
import hmac
from urllib.parse import parse_qs, urlparse

import pytest

from app.extensions import db
from app.models import EventoPagamento, Pedido, Product, User
from app.services import mercadopago
from app.services.mercadopago import ErroMercadoPago, assinatura_valida

SEGREDO = "segredo-de-teste"


class MPFalso:
    """Faz o papel da API do Mercado Pago e guarda cada chamada recebida."""

    def __init__(self):
        self.chamadas = []
        self.pagamentos = {}
        self.fora_do_ar = False

    def __call__(self, metodo, caminho, corpo=None, idempotencia=None):
        self.chamadas.append({"metodo": metodo, "caminho": caminho, "corpo": corpo, "idempotencia": idempotencia})
        if self.fora_do_ar:
            raise ErroMercadoPago("fora do ar")
        if caminho == "/checkout/preferences":
            ref = corpo["external_reference"]
            return {"id": f"pref-{ref}", "init_point": f"https://mp.exemplo.test/checkout?pref=pref-{ref}"}
        if caminho.startswith("/v1/payments/"):
            pid = caminho.rsplit("/", 1)[1]
            if pid not in self.pagamentos:
                raise ErroMercadoPago("pagamento não encontrado")
            return self.pagamentos[pid]
        raise AssertionError(f"chamada inesperada: {metodo} {caminho}")

    def pagar(self, pid, pedido, status="approved", valor_centavos=None, moeda="BRL"):
        self.pagamentos[str(pid)] = {
            "id": int(pid), "status": status, "external_reference": str(pedido.id), "currency_id": moeda,
            "transaction_amount": (pedido.total_centavos if valor_centavos is None else valor_centavos) / 100,
        }

    def preferencias(self):
        return [c for c in self.chamadas if c["caminho"] == "/checkout/preferences"]


@pytest.fixture()
def mp(monkeypatch):
    falso = MPFalso()
    monkeypatch.setattr(mercadopago, "_requisicao", falso)
    return falso


def prod(slug="caneca-azul"):
    return Product.query.filter_by(slug=slug).first()


def assinar(data_id, request_id="req-1", ts="1731600000000", segredo=SEGREDO):
    manifesto = f"id:{data_id};request-id:{request_id};ts:{ts};"
    v1 = hmac.new(segredo.encode(), manifesto.encode(), hashlib.sha256).hexdigest()
    return {"x-signature": f"ts={ts},v1={v1}", "x-request-id": request_id}


def webhook(client, pid, headers=None, tipo="payment"):
    headers = assinar(pid) if headers is None else headers
    return client.post(f"/pagamento/webhook?data.id={pid}&type={tipo}",
                       json={"type": tipo, "action": "payment.updated", "data": {"id": str(pid)}}, headers=headers)


def no_carrinho(client, quantidade=2):
    client.post(f"/carrinho/adicionar/{prod().id}", data={"quantidade": str(quantidade)})


def token_do_resumo(client):
    client.get("/checkout/")
    with client.session_transaction() as s:
        return s.get("checkout_token")


def fechar_pedido(client, quantidade=2):
    no_carrinho(client, quantidade)
    return client.post("/checkout/confirmar", data={"token": token_do_resumo(client), "entrega": "retirada"})


def ultimo_pedido():
    return Pedido.query.order_by(Pedido.id.desc()).first()


# ---------- Assinatura do webhook (função pura) ----------

def test_assinatura_valida_e_invalida():
    h = assinar("123")
    assert assinatura_valida(h["x-signature"], h["x-request-id"], "123", SEGREDO)
    assert not assinatura_valida(h["x-signature"], h["x-request-id"], "124", SEGREDO)  # id trocado
    assert not assinatura_valida(h["x-signature"], "req-2", "123", SEGREDO)            # request-id trocado
    assert not assinatura_valida(h["x-signature"], h["x-request-id"], "123", "outro")  # segredo errado
    assert not assinatura_valida("", "", "123", SEGREDO)
    assert not assinatura_valida("lixo", "req-1", "123", SEGREDO)
    assert not assinatura_valida(h["x-signature"], h["x-request-id"], "123", "")      # sem segredo configurado


def test_assinatura_aceita_id_alfanumerico_em_maiusculas():
    h = assinar("abc123")
    assert assinatura_valida(h["x-signature"], h["x-request-id"], "ABC123", SEGREDO)


# ---------- Resumo ----------

def test_checkout_exige_login(client):
    r = client.get("/checkout/")
    assert r.status_code == 302 and parse_qs(urlparse(r.headers["Location"]).query)["next"] == ["/checkout/"]


def test_checkout_com_carrinho_vazio_volta_pro_carrinho(client_cliente):
    r = client_cliente.get("/checkout/")
    assert r.status_code == 302 and r.headers["Location"] == "/carrinho/"


def test_carrinho_tem_botao_finalizar_compra(client_cliente, catalogo):
    no_carrinho(client_cliente)
    assert 'href="/checkout/"' in client_cliente.get("/carrinho/").get_data(as_text=True)


def test_resumo_mostra_itens_e_retirada(client_cliente, catalogo, mp):
    no_carrinho(client_cliente)
    html = client_cliente.get("/checkout/").get_data(as_text=True)
    assert "Caneca azul" in html and "R$ 110,00" in html
    assert "Retirada no ateliê" in html and "Rua Espanha, 532" in html


# ---------- Confirmar: pedido + preferência ----------

def test_confirmar_cria_pedido_e_manda_pro_mercado_pago(client_cliente, catalogo, mp):
    r = fechar_pedido(client_cliente, quantidade=2)
    pedido = ultimo_pedido()
    assert r.status_code == 303 and r.headers["Location"] == f"https://mp.exemplo.test/checkout?pref=pref-{pedido.id}"
    assert pedido.status == "aguardando_pagamento" and pedido.entrega_tipo == "retirada"
    assert pedido.total_centavos == 11000 and pedido.frete_centavos == 0
    assert pedido.itens[0].nome_produto == "Caneca azul" and pedido.itens[0].preco_unitario_centavos == 5500
    assert pedido.mp_preference_id == f"pref-{pedido.id}"
    assert prod().estoque == 3  # estoque NÃO baixa ao criar o pedido
    with client_cliente.session_transaction() as s:
        assert not s.get("carrinho")


def test_preferencia_tem_so_o_necessario(client_cliente, catalogo, mp):
    fechar_pedido(client_cliente, quantidade=1)
    pedido = ultimo_pedido()
    chamada = mp.preferencias()[0]
    corpo = chamada["corpo"]
    assert chamada["idempotencia"] == f"pedido-{pedido.id}"
    assert corpo["external_reference"] == str(pedido.id)
    assert sum(round(i["unit_price"] * 100) * i["quantity"] for i in corpo["items"]) == pedido.total_centavos == 5500
    assert all(i["currency_id"] == "BRL" for i in corpo["items"])
    assert corpo["back_urls"]["success"] == f"https://loja.exemplo.test/checkout/retorno/{pedido.id}"
    assert corpo["notification_url"] == "https://loja.exemplo.test/pagamento/webhook"
    assert corpo["payer"]["email"] == "cliente@exemplo.com"
    assert {"id": "ticket"} in corpo["payment_methods"]["excluded_payment_types"]  # sem boleto
    assert "card" not in str(corpo).lower().replace("card_", "")  # nada de dado de cartão


def test_entrega_em_casa_nao_cria_pedido(client_cliente, catalogo, mp):
    no_carrinho(client_cliente)
    r = client_cliente.post("/checkout/confirmar", data={"token": token_do_resumo(client_cliente), "entrega": "entrega"})
    assert r.headers["Location"] == "/checkout/" and Pedido.query.count() == 0


def test_clique_duplo_cria_um_pedido_so(client_cliente, catalogo, mp):
    no_carrinho(client_cliente)
    token = token_do_resumo(client_cliente)
    client_cliente.post("/checkout/confirmar", data={"token": token, "entrega": "retirada"})
    r = client_cliente.post("/checkout/confirmar", data={"token": token, "entrega": "retirada"})
    assert Pedido.query.count() == 1 and len(mp.preferencias()) == 1
    assert r.headers["Location"] == "/conta/pedidos"


def test_estoque_que_mudou_no_meio_nao_cria_pedido(client_cliente, catalogo, mp):
    no_carrinho(client_cliente, 3)
    token = token_do_resumo(client_cliente)
    prod().estoque = 1
    db.session.commit()
    r = client_cliente.post("/checkout/confirmar", data={"token": token, "entrega": "retirada"})
    assert r.headers["Location"] == "/checkout/" and Pedido.query.count() == 0


def test_preco_e_quantidade_do_formulario_sao_ignorados(client_cliente, catalogo, mp):
    no_carrinho(client_cliente, 1)
    client_cliente.post("/checkout/confirmar", data={"token": token_do_resumo(client_cliente), "entrega": "retirada",
                                                    "total": "1", "preco": "1", "quantidade": "50"})
    assert ultimo_pedido().total_centavos == 5500


def test_mercado_pago_fora_do_ar_guarda_o_pedido_pra_pagar_depois(client_cliente, catalogo, mp):
    mp.fora_do_ar = True
    r = fechar_pedido(client_cliente)
    pedido = ultimo_pedido()
    assert pedido.status == "aguardando_pagamento" and pedido.mp_init_point is None
    assert r.headers["Location"] == f"/conta/pedidos/{pedido.id}"
    html = client_cliente.get(f"/conta/pedidos/{pedido.id}").get_data(as_text=True)
    assert f'action="/checkout/pagar/{pedido.id}"' in html


def test_sem_mercado_pago_configurado_nao_vende(app, client_cliente, catalogo, mp):
    app.config["MP_ACCESS_TOKEN"] = ""
    no_carrinho(client_cliente)
    assert "Pagamento indisponível" in client_cliente.get("/checkout/").get_data(as_text=True)
    client_cliente.post("/checkout/confirmar", data={"token": token_do_resumo(client_cliente), "entrega": "retirada"})
    assert Pedido.query.count() == 0 and mp.chamadas == []


# ---------- Webhook ----------

def test_webhook_aprovado_paga_e_baixa_estoque(client_cliente, catalogo, mp):
    fechar_pedido(client_cliente, quantidade=2)
    pedido = ultimo_pedido()
    mp.pagar(555, pedido)
    assert webhook(client_cliente, 555).status_code == 200
    db.session.refresh(pedido)
    assert pedido.status == "pago" and pedido.pago_em is not None and pedido.mp_payment_id == "555"
    assert prod().estoque == 1 and not pedido.estoque_insuficiente


def test_webhook_repetido_nao_paga_duas_vezes(client_cliente, catalogo, mp):
    fechar_pedido(client_cliente, quantidade=1)
    mp.pagar(555, ultimo_pedido())
    for _ in range(3):
        assert webhook(client_cliente, 555).status_code == 200
    assert prod().estoque == 2
    assert EventoPagamento.query.filter_by(mp_payment_id="555").count() == 1


def test_webhook_com_assinatura_errada_e_recusado(client_cliente, catalogo, mp):
    fechar_pedido(client_cliente)
    mp.pagar(555, ultimo_pedido())
    assert webhook(client_cliente, 555, headers=assinar(555, segredo="chute")).status_code == 401
    assert webhook(client_cliente, 555, headers={}).status_code == 401
    assert ultimo_pedido().status == "aguardando_pagamento" and prod().estoque == 3
    assert not [c for c in mp.chamadas if c["caminho"].startswith("/v1/payments")]


@pytest.mark.parametrize("valor, moeda", [(100, "BRL"), (None, "USD")])
def test_valor_ou_moeda_diferente_nao_aprova(client_cliente, catalogo, mp, valor, moeda):
    fechar_pedido(client_cliente)
    mp.pagar(555, ultimo_pedido(), valor_centavos=valor, moeda=moeda)
    webhook(client_cliente, 555)
    assert ultimo_pedido().status == "aguardando_pagamento" and prod().estoque == 3


def test_pagamento_de_pedido_que_nao_existe_e_ignorado(client_cliente, catalogo, mp):
    mp.pagamentos["777"] = {"id": 777, "status": "approved", "external_reference": "99999",
                            "transaction_amount": 10.0, "currency_id": "BRL"}
    assert webhook(client_cliente, 777).status_code == 200
    assert EventoPagamento.query.count() == 0


def test_recusado_continua_aguardando_e_depois_aprova(client_cliente, catalogo, mp):
    fechar_pedido(client_cliente, quantidade=1)
    pedido = ultimo_pedido()
    mp.pagar(1, pedido, status="rejected")
    webhook(client_cliente, 1)
    assert ultimo_pedido().status == "aguardando_pagamento"
    mp.pagar(2, pedido, status="approved")  # tentou de novo com outro cartão
    webhook(client_cliente, 2)
    assert ultimo_pedido().status == "pago" and prod().estoque == 2


def test_cancelado_ou_expirado_cancela_sem_mexer_no_estoque(client_cliente, catalogo, mp):
    fechar_pedido(client_cliente)
    mp.pagar(9, ultimo_pedido(), status="cancelled")
    webhook(client_cliente, 9)
    assert ultimo_pedido().status == "cancelado" and prod().estoque == 3


def test_corrida_pela_ultima_peca(client_cliente, catalogo, mp):
    prod().estoque = 1
    db.session.commit()
    fechar_pedido(client_cliente, quantidade=1)
    primeiro = ultimo_pedido()
    fechar_pedido(client_cliente, quantidade=1)
    segundo = ultimo_pedido()
    mp.pagar(1, primeiro)
    mp.pagar(2, segundo)
    webhook(client_cliente, 1)
    webhook(client_cliente, 2)
    db.session.refresh(primeiro)
    db.session.refresh(segundo)
    assert primeiro.status == segundo.status == "pago"
    assert not primeiro.estoque_insuficiente and segundo.estoque_insuficiente  # a Julia resolve no painel
    assert prod().estoque == 0  # nunca negativo


def test_outros_avisos_sao_ignorados(client_cliente, mp):
    assert webhook(client_cliente, 1, tipo="merchant_order").status_code == 200
    assert mp.chamadas == []


def test_mercado_pago_fora_do_ar_no_webhook_pede_pra_tentar_de_novo(client_cliente, catalogo, mp):
    fechar_pedido(client_cliente)
    mp.fora_do_ar = True
    assert webhook(client_cliente, 555).status_code == 500  # o Mercado Pago reenvia depois
    assert ultimo_pedido().status == "aguardando_pagamento"


def test_webhook_nao_exige_csrf(app, client, catalogo, mp):
    # Quem chama é o Mercado Pago, não um formulário nosso: a proteção é a assinatura
    app.config["WTF_CSRF_ENABLED"] = True
    assert webhook(client, 1, tipo="merchant_order").status_code == 200


# ---------- Volta do Mercado Pago ----------

def test_status_forjado_na_url_nao_aprova(client_cliente, catalogo, mp):
    fechar_pedido(client_cliente)
    pedido = ultimo_pedido()
    html = client_cliente.get(f"/checkout/retorno/{pedido.id}?status=approved&collection_status=approved").get_data(as_text=True)
    assert ultimo_pedido().status == "aguardando_pagamento" and "Pago!" not in html


def test_retorno_confirma_com_o_mercado_pago_mesmo_sem_webhook(client_cliente, catalogo, mp):
    fechar_pedido(client_cliente, quantidade=1)
    pedido = ultimo_pedido()
    mp.pagar(321, pedido)
    html = client_cliente.get(f"/checkout/retorno/{pedido.id}?payment_id=321&status=approved").get_data(as_text=True)
    assert "Pago!" in html and ultimo_pedido().status == "pago"
    webhook(client_cliente, 321)  # o webhook chega depois: nada muda
    assert prod().estoque == 2 and EventoPagamento.query.count() == 1


def test_retorno_aguardando_pix(client_cliente, catalogo, mp):
    fechar_pedido(client_cliente)
    pedido = ultimo_pedido()
    mp.pagar(5, pedido, status="pending")
    html = client_cliente.get(f"/checkout/retorno/{pedido.id}?payment_id=5").get_data(as_text=True)
    assert "Aguardando pagamento" in html


def outro_pedido():
    bruno = User(nome="Bruno", email="bruno@exemplo.com")
    bruno.set_password("senha-segura-123")
    db.session.add(bruno)
    db.session.flush()
    pedido = Pedido(user_id=bruno.id, status="aguardando_pagamento", subtotal_centavos=100,
                    frete_centavos=0, total_centavos=100, entrega_tipo="retirada")
    db.session.add(pedido)
    db.session.commit()
    return pedido


def test_retorno_e_pagar_de_outro_cliente_dao_404(client_cliente, catalogo, mp):
    pedido = outro_pedido()
    assert client_cliente.get(f"/checkout/retorno/{pedido.id}").status_code == 404
    assert client_cliente.post(f"/checkout/pagar/{pedido.id}").status_code == 404
    assert mp.chamadas == []


def test_pagar_depois_cria_preferencia_se_preciso(client_cliente, catalogo, mp):
    mp.fora_do_ar = True
    fechar_pedido(client_cliente)
    mp.fora_do_ar = False
    pedido = ultimo_pedido()
    r = client_cliente.post(f"/checkout/pagar/{pedido.id}")
    assert r.status_code == 303 and r.headers["Location"].startswith("https://mp.exemplo.test/")


def test_pedido_pago_nao_abre_pagamento_de_novo(client_cliente, catalogo, mp):
    fechar_pedido(client_cliente)
    pedido = ultimo_pedido()
    mp.pagar(1, pedido)
    webhook(client_cliente, 1)
    chamadas = len(mp.chamadas)
    r = client_cliente.post(f"/checkout/pagar/{pedido.id}")
    assert r.headers["Location"] == f"/conta/pedidos/{pedido.id}" and len(mp.chamadas) == chamadas


def test_pedido_pago_duas_vezes_baixa_estoque_uma_vez_so(client_cliente, catalogo, mp):
    # Achado do teste de mutação: dois pagamentos DIFERENTES aprovados pro mesmo pedido
    # (ex.: dois Pix). O segundo fica registrado pra Julia devolver, mas não baixa estoque de novo.
    fechar_pedido(client_cliente, quantidade=1)
    pedido = ultimo_pedido()
    mp.pagar(1, pedido)
    mp.pagar(2, pedido)
    webhook(client_cliente, 1)
    webhook(client_cliente, 2)
    assert prod().estoque == 2 and ultimo_pedido().mp_payment_id == "1"
    assert EventoPagamento.query.filter_by(pedido_id=pedido.id, status="approved").count() == 2
