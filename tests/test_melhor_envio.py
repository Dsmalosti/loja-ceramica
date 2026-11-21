"""[back/melhor-envio] Frete pelo Melhor Envio: cotação, escolha no checkout e frete no pedido.

Nada sai para a internet: melhorenvio._requisicao é substituída por um falso que guarda o que recebeu.
"""
import io
import json
import re
import urllib.request

import pytest
from test_checkout import mp, no_carrinho, prod  # noqa: F401  (fixture mp)

from app.extensions import db
from app.models import Endereco, Pedido, User
from app.services import melhorenvio

COTACAO = [
    {"id": 2, "name": "SEDEX", "price": "41.20", "custom_price": "39.90", "delivery_time": 3, "custom_delivery_time": 4,
     "company": {"id": 1, "name": "Correios"}},
    {"id": 1, "name": "PAC", "price": "25.00", "custom_price": "23.45", "delivery_time": 8, "custom_delivery_time": 9,
     "company": {"id": 1, "name": "Correios"}},
    {"id": 3, "name": ".Package", "error": "Transportadora não atende este trecho.", "company": {"id": 2, "name": "Jadlog"}},
]


class MEFalso:
    def __init__(self):
        self.corpos = []
        self.resposta = json.loads(json.dumps(COTACAO))
        self.fora_do_ar = False

    def __call__(self, corpo):
        self.corpos.append(corpo)
        if self.fora_do_ar:
            raise melhorenvio.ErroMelhorEnvio("fora do ar")
        return self.resposta


@pytest.fixture()
def me(app, monkeypatch, catalogo):
    app.config.update(MELHOR_ENVIO_TOKEN="token-falso", MELHOR_ENVIO_CEP_ORIGEM="12030000",
                      MELHOR_ENVIO_USER_AGENT="Malosti (contato@exemplo.test)", MELHOR_ENVIO_SERVICOS="")
    caneca = prod()
    caneca.peso_gramas, caneca.altura_cm, caneca.largura_cm, caneca.comprimento_cm = 450, 12, 10, 10
    db.session.commit()
    falso = MEFalso()
    monkeypatch.setattr(melhorenvio, "_requisicao", falso)
    return falso


def com_endereco(cep="01310100"):
    usuario = User.query.filter_by(email="cliente@exemplo.com").one()
    db.session.add(Endereco(user_id=usuario.id, cep=cep, logradouro="Avenida Paulista", numero="1000",
                            complemento="ap 12", bairro="Bela Vista", cidade="São Paulo", uf="SP"))
    db.session.commit()


def resumo_casa(client):
    html = client.get("/checkout/?entrega=casa").get_data(as_text=True)
    with client.session_transaction() as s:
        return html, s.get("checkout_token")


def confirmar(client, token, servico="1", **extra):
    return client.post("/checkout/confirmar", data={"token": token, "entrega": "entrega", "servico": servico, **extra})


# ---------- Serviço ----------

def test_cotacao_monta_o_pedido_para_a_api(app, me):
    linha = type("Linha", (), {"produto": prod(), "quantidade": 2, "preco_unitario_centavos": 5500})()
    with app.app_context():
        melhorenvio.cotar("01310-100", [linha])
    corpo = me.corpos[0]
    assert corpo["from"] == {"postal_code": "12030000"} and corpo["to"] == {"postal_code": "01310100"}
    assert corpo["products"] == [{"id": str(prod().id), "width": 10, "height": 12, "length": 10, "weight": 0.45,
                                  "insurance_value": 55.0, "quantity": 2}]
    assert corpo["options"] == {"receipt": False, "own_hand": False} and "services" not in corpo


def test_cotacao_usa_preco_e_prazo_da_conta_e_ignora_servico_com_erro(app, me):
    linha = type("Linha", (), {"produto": prod(), "quantidade": 1, "preco_unitario_centavos": 5500})()
    opcoes = melhorenvio.cotar("01310100", [linha])
    assert [(o.rotulo, o.preco_centavos, o.prazo_dias) for o in opcoes] == [
        ("Correios PAC", 2345, 9), ("Correios SEDEX", 3990, 4)]


def test_servicos_escolhidos_no_env_vao_na_cotacao(app, me):
    app.config["MELHOR_ENVIO_SERVICOS"] = "1,2"
    linha = type("Linha", (), {"produto": prod(), "quantidade": 1, "preco_unitario_centavos": 5500})()
    melhorenvio.cotar("01310100", [linha])
    assert me.corpos[0]["services"] == "1,2"


def test_produto_sem_medidas_nao_cota(app, me):
    prod().peso_gramas = None
    db.session.commit()
    linha = type("Linha", (), {"produto": prod(), "quantidade": 1, "preco_unitario_centavos": 5500})()
    with pytest.raises(melhorenvio.ErroMelhorEnvio):
        melhorenvio.cotar("01310100", [linha])
    opcoes, erro = melhorenvio.cotar_sem_erro("01310100", [linha])
    assert opcoes == [] and "Não deu para calcular o frete" in erro
    assert me.corpos == []  # nem chamou a API


@pytest.mark.parametrize("cep", ["123", "", "abcdefgh"])
def test_cep_invalido_nao_cota(app, me, cep):
    with pytest.raises(melhorenvio.ErroMelhorEnvio):
        melhorenvio.cotar(cep, [])


def test_requisicao_vai_para_o_sandbox_com_token_e_user_agent(app, monkeypatch):
    app.config.update(MELHOR_ENVIO_TOKEN="token-falso", MELHOR_ENVIO_USER_AGENT="Malosti (contato@exemplo.test)",
                      MELHOR_ENVIO_AMBIENTE="sandbox")
    recebido = {}

    def urlopen_falso(req, timeout):
        recebido.update(url=req.full_url, headers=dict(req.header_items()), timeout=timeout)
        return io.BytesIO(b"[]")

    monkeypatch.setattr(urllib.request, "urlopen", urlopen_falso)
    assert melhorenvio._requisicao({"x": 1}) == []
    assert recebido["url"] == "https://sandbox.melhorenvio.com.br/api/v2/me/shipment/calculate"
    assert recebido["headers"]["Authorization"] == "Bearer token-falso"
    assert recebido["headers"]["User-agent"] == "Malosti (contato@exemplo.test)"
    assert recebido["timeout"] == 10


def test_sem_token_o_frete_fica_desligado(app):
    assert melhorenvio.configurado() is False


# ---------- Checkout ----------

def test_resumo_oferece_retirar_ou_receber_em_casa(client_cliente, me):
    no_carrinho(client_cliente, 1)
    html = client_cliente.get("/checkout/").get_data(as_text=True)
    assert "Retirar no ateliê" in html and "Receber em casa" in html
    assert 'name="entrega" value="retirada"' in html and me.corpos == []  # retirada não cota


def test_receber_em_casa_sem_endereco_pede_o_cadastro(client_cliente, me):
    no_carrinho(client_cliente, 1)
    html, _ = resumo_casa(client_cliente)
    assert "Cadastrar endereço" in html and "next=" in html
    assert re.search(r'<button type="submit" class="botao botao--ambar"\s+disabled', html)  # sem endereço, não paga


def test_receber_em_casa_mostra_as_opcoes_cotadas(client_cliente, me):
    com_endereco()
    no_carrinho(client_cliente, 2)
    html, _ = resumo_casa(client_cliente)
    assert "Avenida Paulista, 1000" in html
    assert "Correios PAC" in html and "R$ 23,45" in html and "Correios SEDEX" in html and "R$ 39,90" in html
    assert "Jadlog" not in html  # serviço com erro fica de fora
    assert me.corpos[0]["to"] == {"postal_code": "01310100"} and me.corpos[0]["products"][0]["quantity"] == 2


def test_pedido_com_entrega_leva_frete_endereco_e_servico(client_cliente, me, mp):  # noqa: F811
    com_endereco()
    no_carrinho(client_cliente, 2)
    _, token = resumo_casa(client_cliente)
    r = confirmar(client_cliente, token, servico="2")
    assert r.status_code == 303
    pedido = Pedido.query.one()
    assert pedido.entrega_tipo == "entrega" and pedido.frete_centavos == 3990
    assert pedido.total_centavos == 11000 + 3990
    assert pedido.entrega_cep == "01310100" and pedido.entrega_complemento == "ap 12"
    assert pedido.frete_servico == "Correios SEDEX" and pedido.frete_prazo_dias == 4
    itens = mp.preferencias()[0]["corpo"]["items"]
    assert {"id": "frete", "title": "Frete", "quantity": 1, "unit_price": 39.9, "currency_id": "BRL"} in itens


def test_servico_que_nao_foi_cotado_e_recusado(client_cliente, me, mp):  # noqa: F811
    com_endereco()
    no_carrinho(client_cliente, 1)
    _, token = resumo_casa(client_cliente)
    r = confirmar(client_cliente, token, servico="3", frete_centavos="1")  # Jadlog estava indisponível
    assert r.status_code == 302 and Pedido.query.count() == 0


def test_frete_que_mudou_desde_o_resumo_avisa_antes_de_pagar(client_cliente, me, mp):  # noqa: F811
    com_endereco()
    no_carrinho(client_cliente, 1)
    _, token = resumo_casa(client_cliente)
    me.resposta[1]["custom_price"] = "29.00"  # o PAC subiu entre o resumo e a confirmação
    r = confirmar(client_cliente, token, servico="1", follow_redirects=False)
    assert r.status_code == 302 and Pedido.query.count() == 0
    pagina = client_cliente.get(r.headers["Location"]).get_data(as_text=True)
    assert "O frete de Correios PAC mudou" in pagina


def test_melhor_envio_fora_do_ar_nao_cria_pedido(client_cliente, me, mp):  # noqa: F811
    com_endereco()
    no_carrinho(client_cliente, 1)
    _, token = resumo_casa(client_cliente)
    me.fora_do_ar = True
    r = confirmar(client_cliente, token, servico="1")
    assert r.status_code == 302 and Pedido.query.count() == 0


def test_entrega_sem_endereco_nao_cria_pedido(client_cliente, me, mp):  # noqa: F811
    no_carrinho(client_cliente, 1)
    _, token = resumo_casa(client_cliente)
    assert confirmar(client_cliente, token).status_code == 302 and Pedido.query.count() == 0


def test_retirada_continua_sem_frete_com_o_melhor_envio_ligado(client_cliente, me, mp):  # noqa: F811
    no_carrinho(client_cliente, 1)
    client_cliente.get("/checkout/")
    with client_cliente.session_transaction() as s:
        token = s["checkout_token"]
    client_cliente.post("/checkout/confirmar", data={"token": token, "entrega": "retirada"})
    pedido = Pedido.query.one()
    assert pedido.entrega_tipo == "retirada" and pedido.frete_centavos == 0 and pedido.frete_servico is None


# ---------- Endereço volta para o checkout ----------

ENDERECO = {"cep": "01310-100", "logradouro": "Avenida Paulista", "numero": "1000", "complemento": "",
            "bairro": "Bela Vista", "cidade": "São Paulo", "uf": "SP"}


def test_salvar_endereco_volta_para_o_checkout(client_cliente):
    r = client_cliente.post("/conta/endereco", data={**ENDERECO, "next": "/checkout/?entrega=casa"})
    assert r.status_code == 302 and r.headers["Location"].endswith("/checkout/?entrega=casa")


def test_next_externo_e_ignorado(client_cliente):
    r = client_cliente.post("/conta/endereco", data={**ENDERECO, "next": "https://golpe.exemplo/"})
    assert r.headers["Location"].endswith("/conta/endereco")


def test_pagina_do_produto_fala_do_frete_pelo_cep(client, me):
    assert "frete é calculado pelo CEP" in client.get(f"/loja/{prod().slug}").get_data(as_text=True)
