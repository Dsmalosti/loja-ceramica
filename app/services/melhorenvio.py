"""Cotação de frete pelo Melhor Envio (https://docs.melhorenvio.com.br).

[back/melhor-envio] Novo. Só biblioteca padrão (urllib), como o Mercado Pago e o Brevo.

- POST /api/v2/me/shipment/calculate com os produtos do carrinho: medidas em cm, peso em kg,
  valor declarado por unidade (o Melhor Envio multiplica pela quantidade).
- A resposta é uma lista de serviços (PAC, SEDEX, Jadlog...). O preço vem como texto ("37.79");
  usamos o custom_price e o custom_delivery_time, que já trazem as taxas e prazos da conta.
- Serviço indisponível para o trecho vem com o campo "error": fica de fora da lista.
- O preço NUNCA vem do formulário: o checkout cota de novo na hora de confirmar o pedido.
- Sem MELHOR_ENVIO_TOKEN no .env, o site segue só com retirada no ateliê.
"""
import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from flask import current_app

log = logging.getLogger(__name__)

URLS = {
    "sandbox": "https://sandbox.melhorenvio.com.br",
    "producao": "https://melhorenvio.com.br",
}
CAMINHO_COTACAO = "/api/v2/me/shipment/calculate"


class ErroMelhorEnvio(Exception):
    """Não deu para cotar (a mensagem é só para o log; a pessoa vê um aviso genérico)."""


@dataclass(frozen=True)
class OpcaoFrete:
    id: int
    nome: str            # "PAC", "SEDEX", ".Package"
    empresa: str         # "Correios", "Jadlog"
    preco_centavos: int
    prazo_dias: int | None

    @property
    def rotulo(self):
        return f"{self.empresa} {self.nome}".strip()


def configurado():
    c = current_app.config
    return bool(c.get("MELHOR_ENVIO_TOKEN") and c.get("MELHOR_ENVIO_CEP_ORIGEM") and c.get("MELHOR_ENVIO_USER_AGENT"))


def _requisicao(corpo):
    """Faz o POST da cotação. Separada para os testes substituírem (nada sai pra internet)."""
    c = current_app.config
    base = URLS.get(c.get("MELHOR_ENVIO_AMBIENTE", "sandbox"), URLS["sandbox"])
    req = urllib.request.Request(
        base + CAMINHO_COTACAO,
        data=json.dumps(corpo).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {c['MELHOR_ENVIO_TOKEN']}",
            # A API exige o nome do app e um e-mail de contato técnico (vem do .env, nunca do código)
            "User-Agent": c["MELHOR_ENVIO_USER_AGENT"],
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resposta:
            return json.loads(resposta.read().decode())
    except urllib.error.HTTPError as erro:
        raise ErroMelhorEnvio(f"HTTP {erro.code} na cotação") from None
    except (urllib.error.URLError, TimeoutError, ValueError) as erro:
        raise ErroMelhorEnvio(f"{type(erro).__name__} na cotação") from None


def _produtos(linhas):
    produtos = []
    for linha in linhas:
        p = linha.produto
        medidas = (p.largura_cm, p.altura_cm, p.comprimento_cm, p.peso_gramas)
        if not all(medidas):
            raise ErroMelhorEnvio(f"produto {p.id} sem peso ou medidas")
        produtos.append({
            "id": str(p.id),
            "width": p.largura_cm,
            "height": p.altura_cm,
            "length": p.comprimento_cm,
            "weight": round(p.peso_gramas / 1000, 3),
            "insurance_value": round(linha.preco_unitario_centavos / 100, 2),
            "quantity": linha.quantidade,
        })
    return produtos


def _centavos(texto):
    try:
        return int((Decimal(str(texto)) * 100).quantize(Decimal("1")))
    except (InvalidOperation, TypeError, ValueError):
        return None


def cotar(cep_destino, linhas):
    """Lista de OpcaoFrete, da mais barata para a mais cara. Lança ErroMelhorEnvio se não der para cotar."""
    cep_destino = "".join(c for c in str(cep_destino or "") if c.isdigit())
    if len(cep_destino) != 8:
        raise ErroMelhorEnvio("CEP de destino inválido")
    corpo = {
        "from": {"postal_code": current_app.config["MELHOR_ENVIO_CEP_ORIGEM"]},
        "to": {"postal_code": cep_destino},
        "products": _produtos(linhas),
        "options": {"receipt": False, "own_hand": False},
    }
    servicos = current_app.config.get("MELHOR_ENVIO_SERVICOS", "").strip()
    if servicos:
        corpo["services"] = servicos
    resposta = _requisicao(corpo)
    if not isinstance(resposta, list):
        raise ErroMelhorEnvio("resposta inesperada da cotação")

    opcoes = []
    for item in resposta:
        if not isinstance(item, dict) or item.get("error"):
            continue  # serviço que não atende esse trecho
        preco = _centavos(item.get("custom_price") or item.get("price"))
        if preco is None or preco <= 0 or not isinstance(item.get("id"), int):
            continue
        prazo = item.get("custom_delivery_time") or item.get("delivery_time")
        opcoes.append(OpcaoFrete(
            id=item["id"],
            nome=str(item.get("name") or "").strip(),
            empresa=str((item.get("company") or {}).get("name") or "").strip(),
            preco_centavos=preco,
            prazo_dias=prazo if isinstance(prazo, int) else None,
        ))
    return sorted(opcoes, key=lambda o: (o.preco_centavos, o.prazo_dias or 99))


def cotar_sem_erro(cep_destino, linhas):
    """Para a tela: devolve (opções, mensagem de erro para a pessoa ou None). Nunca lança."""
    try:
        opcoes = cotar(cep_destino, linhas)
    except ErroMelhorEnvio as erro:
        log.warning("Cotação do Melhor Envio falhou: %s", erro)
        return [], "Não deu para calcular o frete agora. Tente de novo em alguns minutos ou escolha a retirada no ateliê."
    if not opcoes:
        return [], "Nenhuma transportadora atende esse CEP para estes produtos. Fale com o ateliê pelo WhatsApp."
    return opcoes, None
