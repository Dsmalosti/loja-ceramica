"""E-mails (Brevo simulado: nada sai pra internet) e recuperação de senha."""
import re
import urllib.error

import pytest

from app.extensions import db
from app.models import User
from app.services import email, mensagens

from test_checkout import fechar_pedido, mp, ultimo_pedido, webhook  # noqa: F401  (fixture mp)


@pytest.fixture()
def enviados(monkeypatch):
    """Guarda cada e-mail que sairia pelo Brevo."""
    lista = []
    monkeypatch.setattr(email, "_requisicao", lambda corpo, chave: lista.append({**corpo, "_chave": chave}) or 201)
    return lista


def _link(texto):
    return re.search(r"https://loja\.exemplo\.test(/redefinir-senha/\S+)", texto).group(1)


# ---------- serviço ----------

def test_enviar_monta_o_corpo_do_brevo(app, enviados):
    assert email.enviar("a@b.com", "Oi", "texto", "<p>html</p>", nome_para="Ana") is True
    e = enviados[0]
    assert e["to"] == [{"email": "a@b.com", "name": "Ana"}]
    assert e["sender"]["email"] == "loja@exemplo.test" and e["subject"] == "Oi"
    assert e["textContent"] == "texto" and e["htmlContent"] == "<p>html</p>"
    assert e["_chave"] == "chave-brevo-falsa"


def test_sem_chave_nao_envia_e_nao_quebra(app, enviados):
    app.config["BREVO_API_KEY"] = ""
    assert email.enviar("a@b.com", "Oi", "texto") is False and enviados == []


def test_falha_do_brevo_nao_lanca_erro(app, monkeypatch):
    def quebra(corpo, chave):
        raise urllib.error.HTTPError("u", 401, "x", {}, None)
    monkeypatch.setattr(email, "_requisicao", quebra)
    assert email.enviar("a@b.com", "Oi", "texto") is False
    monkeypatch.setattr(email, "_requisicao", lambda c, k: (_ for _ in ()).throw(TimeoutError()))
    assert email.enviar("a@b.com", "Oi", "texto") is False


# ---------- recuperação de senha ----------

def test_pedir_recuperacao_envia_link_e_nao_revela_quem_tem_conta(client, criar_usuario, enviados):
    criar_usuario(email="cliente@exemplo.com")
    existe = client.post("/esqueci-senha", data={"email": "Cliente@Exemplo.com"}, follow_redirects=True)
    nao_existe = client.post("/esqueci-senha", data={"email": "ninguem@exemplo.com"}, follow_redirects=True)
    msg = "Se esse e-mail tiver conta".encode()
    assert msg in existe.data and msg in nao_existe.data
    assert len(enviados) == 1 and enviados[0]["to"][0]["email"] == "cliente@exemplo.com"


def test_link_troca_a_senha_e_so_vale_uma_vez(client, criar_usuario, enviados):
    criar_usuario(email="cliente@exemplo.com", senha="senha-antiga-123")
    client.post("/esqueci-senha", data={"email": "cliente@exemplo.com"})
    caminho = _link(enviados[0]["textContent"])

    assert client.get(caminho).status_code == 200
    r = client.post(caminho, data={"senha": "senha-nova-456", "confirmacao": "senha-nova-456"})
    assert r.status_code == 302 and r.headers["Location"].endswith("/entrar")

    assert User.query.filter_by(email="cliente@exemplo.com").one().check_password("senha-nova-456")
    # Segundo uso do mesmo link é recusado
    r = client.post(caminho, data={"senha": "outra-senha-789", "confirmacao": "outra-senha-789"})
    assert r.status_code == 302 and r.headers["Location"].endswith("/esqueci-senha")
    assert User.query.filter_by(email="cliente@exemplo.com").one().check_password("senha-nova-456")


def test_redefinir_valida_a_senha(client, criar_usuario, enviados):
    criar_usuario(email="cliente@exemplo.com", senha="senha-antiga-123")
    client.post("/esqueci-senha", data={"email": "cliente@exemplo.com"})
    caminho = _link(enviados[0]["textContent"])
    for dados in ({"senha": "curta", "confirmacao": "curta"},
                  {"senha": "senha-nova-456", "confirmacao": "diferente-456"}):
        assert client.post(caminho, data=dados).status_code == 200
    assert User.query.filter_by(email="cliente@exemplo.com").one().check_password("senha-antiga-123")


def test_token_adulterado_ou_expirado_e_recusado(client, app, criar_usuario):
    usuario = criar_usuario()
    token = mensagens.gerar_token_senha(usuario)
    assert mensagens.usuario_do_token(token).id == usuario.id
    assert mensagens.usuario_do_token(token + "x") is None
    assert mensagens.usuario_do_token("lixo") is None
    assert client.get(f"/redefinir-senha/{token}x").status_code == 302
    # Expira: com validade 0 o token recém-criado já não vale
    assert mensagens.usuario_do_token(token) is not None
    antigo, mensagens.VALIDADE_SENHA = mensagens.VALIDADE_SENHA, -1
    try:
        assert mensagens.usuario_do_token(token) is None
    finally:
        mensagens.VALIDADE_SENHA = antigo


def test_conta_desativada_nao_recupera(client, criar_usuario, enviados):
    usuario = criar_usuario(email="cliente@exemplo.com")
    usuario.ativo = False
    db.session.commit()
    client.post("/esqueci-senha", data={"email": "cliente@exemplo.com"})
    assert enviados == []


def test_login_tem_link_esqueci_senha(client):
    assert b"/esqueci-senha" in client.get("/entrar").data


# ---------- pedido pago ----------

def test_pedido_pago_avisa_cliente_e_julia_uma_vez(client_cliente, catalogo, mp, enviados):  # noqa: F811
    fechar_pedido(client_cliente, quantidade=2)
    pedido = ultimo_pedido()
    mp.pagar(555, pedido)
    for _ in range(3):  # webhook repetido não repete e-mail
        assert webhook(client_cliente, 555).status_code == 200

    assert len(enviados) == 2
    cliente, julia = enviados
    assert cliente["to"][0]["email"] == "cliente@exemplo.com"
    assert f"#{pedido.id}" in cliente["subject"] and "Caneca azul" in cliente["textContent"]
    assert julia["to"][0]["email"] == "julia@exemplo.test"
    assert f"/admin/pedidos/{pedido.id}" in julia["textContent"]


def test_pedido_nao_pago_nao_envia_email(client_cliente, catalogo, mp, enviados):  # noqa: F811
    fechar_pedido(client_cliente)
    mp.pagar(9, ultimo_pedido(), status="rejected")
    webhook(client_cliente, 9)
    assert enviados == []


def test_falha_no_email_nao_desfaz_o_pagamento(client_cliente, catalogo, mp, monkeypatch):  # noqa: F811
    monkeypatch.setattr(email, "_requisicao", lambda c, k: (_ for _ in ()).throw(OSError("rede fora")))
    fechar_pedido(client_cliente)
    mp.pagar(7, ultimo_pedido())
    assert webhook(client_cliente, 7).status_code == 200
    assert ultimo_pedido().status == "pago"


def test_sem_email_da_julia_avisa_so_a_cliente(client_cliente, app, catalogo, mp, enviados):  # noqa: F811
    app.config["EMAIL_AVISO_PEDIDOS"] = ""
    fechar_pedido(client_cliente)
    mp.pagar(8, ultimo_pedido())
    webhook(client_cliente, 8)
    assert [e["to"][0]["email"] for e in enviados] == ["cliente@exemplo.com"]


# ---------- [back/emails-brevo] respostas e conteúdo ----------

def test_resposta_vai_para_o_ateliê_por_padrão(app, enviados):
    email.enviar("a@b.com", "Oi", "texto")
    assert enviados[0]["replyTo"] == {"email": "loja@exemplo.test"}


def test_resposta_pode_ir_para_outra_pessoa(app, enviados):
    email.enviar("a@b.com", "Oi", "texto", responder_para="cliente@exemplo.com")
    assert enviados[0]["replyTo"] == {"email": "cliente@exemplo.com"}


def test_aviso_da_julia_responde_direto_para_a_cliente(client_cliente, catalogo, mp, enviados):  # noqa: F811
    fechar_pedido(client_cliente)
    mp.pagar(556, ultimo_pedido())
    webhook(client_cliente, 556)
    cliente, julia = enviados
    assert cliente["replyTo"] == {"email": "loja@exemplo.test"}  # cliente responde para o ateliê
    assert julia["replyTo"] == {"email": "cliente@exemplo.com"}  # Julia responde para a cliente


def test_email_da_retirada_diz_onde_e_quando_sem_linha_de_frete(client_cliente, catalogo, mp, enviados):  # noqa: F811
    fechar_pedido(client_cliente)
    pedido = ultimo_pedido()
    mp.pagar(557, pedido)
    webhook(client_cliente, 557)
    cliente, julia = enviados
    for corpo in (cliente["textContent"], cliente["htmlContent"]):
        assert "Rua Espanha, 532" in corpo and "Segunda a sexta" in corpo
        assert f"#{pedido.id}" in corpo
        assert "Frete" not in corpo
    assert "wa.me/" in cliente["htmlContent"]  # dúvida vai para o WhatsApp do ateliê
    assert "Frete" not in julia["textContent"] and "Retirada no ateliê" in julia["textContent"]
