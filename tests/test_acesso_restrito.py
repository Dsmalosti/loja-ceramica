"""Regra da Julia: catálogo aberto; detalhe da peça e carrinho só com login.

Depois do login (ou do cadastro), a pessoa volta para onde estava.
"""
from urllib.parse import parse_qs, urlparse

import pytest

from app.models import Product

SENHA = "senha-segura-123"


def prod(slug="caneca-azul"):
    return Product.query.filter_by(slug=slug).first()


def destino_do_login(resposta):
    """Confere que a resposta manda pro login e devolve o 'next' (endereço de volta)."""
    assert resposta.status_code == 302
    url = urlparse(resposta.headers["Location"])
    assert url.path == "/entrar"
    return parse_qs(url.query).get("next", [None])[0]


def sessao_do(client):
    with client.session_transaction() as s:
        return dict(s.get("carrinho", {}))


# ---------- Catálogo continua aberto ----------

def test_catalogo_abre_sem_login_e_linka_pro_detalhe(client, catalogo):
    r = client.get("/loja/")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Caneca azul" in html and "R$ 55,00" in html
    assert 'href="/loja/caneca-azul"' in html


# Um cliente por teste: o conftest mantém o app_context aberto e o Flask-Login
# guarda o usuário em `g`, que vazaria de um cliente de teste pro outro.
def test_catalogo_avisa_visitante_que_detalhe_pede_login(client, catalogo):
    html = client.get("/loja/").get_data(as_text=True)
    assert "Entre na sua conta" in html
    assert 'href="/entrar?next=/loja/"' in html


def test_catalogo_nao_mostra_aviso_pra_quem_esta_logado(client_cliente, catalogo):
    assert "Entre na sua conta" not in client_cliente.get("/loja/").get_data(as_text=True)


# ---------- Detalhe da peça ----------

def test_detalhe_sem_login_manda_pro_login_com_endereco_de_volta(client, catalogo):
    assert destino_do_login(client.get("/loja/caneca-azul")) == "/loja/caneca-azul"


def test_tela_de_login_guarda_o_destino_e_explica_o_motivo(client, catalogo):
    html = client.get("/loja/caneca-azul", follow_redirects=True).get_data(as_text=True)
    assert 'name="next" value="/loja/caneca-azul"' in html
    assert "ver os detalhes da peça" in html


def test_depois_do_login_volta_pra_peca(client, criar_usuario, catalogo):
    criar_usuario(email="ana@exemplo.com")
    r = client.post("/entrar", data={"email": "ana@exemplo.com", "senha": SENHA,
                                     "next": "/loja/caneca-azul"})
    assert r.status_code == 302 and r.headers["Location"] == "/loja/caneca-azul"
    assert "Caneca azul" in client.get("/loja/caneca-azul").get_data(as_text=True)


def test_cadastro_tambem_volta_pra_peca(client, catalogo):
    r = client.post("/cadastro", data={"nome": "Bia", "email": "bia@exemplo.com", "senha": SENHA,
                                       "confirmacao": SENHA, "next": "/loja/caneca-azul"})
    assert r.status_code == 302 and r.headers["Location"] == "/loja/caneca-azul"


def test_cadastro_ignora_destino_externo(client):
    r = client.post("/cadastro", data={"nome": "Bia", "email": "bia@exemplo.com", "senha": SENHA,
                                       "confirmacao": SENHA, "next": "https://evil.com/"})
    assert r.status_code == 302 and r.headers["Location"] == "/conta"


def test_link_criar_conta_do_login_leva_o_destino(client):
    html = client.get("/entrar?next=/loja/caneca-azul").get_data(as_text=True)
    assert 'href="/cadastro?next=/loja/caneca-azul"' in html


def test_peca_inativa_continua_404_pra_quem_esta_logado(client_cliente, catalogo):
    assert client_cliente.get("/loja/caneca-oculta").status_code == 404


# ---------- Carrinho ----------

def test_carrinho_sem_login_manda_pro_login(client):
    assert destino_do_login(client.get("/carrinho/")) == "/carrinho/"


def test_adicionar_sem_login_volta_pra_peca_e_nao_pro_post(client, catalogo):
    r = client.post(f"/carrinho/adicionar/{prod().id}", data={"quantidade": "1"})
    assert destino_do_login(r) == "/loja/caneca-azul"
    assert sessao_do(client) == {}


def test_adicionar_produto_inexistente_sem_login_volta_pra_loja(client):
    # Sem login não revela se o produto existe: só manda entrar
    assert destino_do_login(client.post("/carrinho/adicionar/99999")) == "/loja/"


@pytest.mark.parametrize("rota", ["/carrinho/atualizar/1", "/carrinho/remover/1", "/carrinho/limpar"])
def test_outras_acoes_do_carrinho_exigem_login(client, catalogo, rota):
    assert destino_do_login(client.post(rota, data={"quantidade": "2"})) == "/carrinho/"


def test_sair_esvazia_o_carrinho(client_cliente, catalogo):
    # Mesmo computador, outra pessoa: o carrinho não pode passar de uma conta pra outra
    client_cliente.post(f"/carrinho/adicionar/{prod().id}", data={"quantidade": "2"})
    assert sessao_do(client_cliente) != {}
    client_cliente.post("/sair")
    assert sessao_do(client_cliente) == {}
