from types import SimpleNamespace

import pytest

from app.models import Product
from app.services import carrinho


class Sessao(dict):
    """Imita a sessão do Flask nas funções que só usam leitura/gravação de chaves."""
    modified = False


def produto(id=1, estoque=5, ativo=True, categoria_ativa=True):
    return SimpleNamespace(id=id, nome=f"Peça {id}", estoque=estoque, ativo=ativo,
                           categoria=SimpleNamespace(ativa=categoria_ativa))


# ---------- Regras puras (sem banco) ----------

@pytest.mark.parametrize("qtd, estoque, esperado", [(2, 5, 2), (9, 5, 5), (0, 5, 0), (-3, 5, 0), (500, 1000, 99), (3, 0, 0)])
def test_limitar(qtd, estoque, esperado):
    assert carrinho.limitar(qtd, estoque) == esperado


def test_ler_ignora_lixo_da_sessao():
    s = Sessao(carrinho={"1": 2, "x": 1, "3": "abc", "4": 0, "-5": 2, "6": 500, "7": None})
    assert carrinho.ler(s) == {1: 2, 6: 99}
    assert carrinho.ler(Sessao(carrinho="qualquer coisa")) == {}
    assert carrinho.ler(Sessao()) == {}


def test_adicionar_soma_e_respeita_o_estoque():
    s, p = Sessao(), produto(estoque=3)
    assert carrinho.adicionar(s, p, 2) == ("ok", 2)
    assert carrinho.adicionar(s, p, 2) == ("limitado", 3)
    assert carrinho.quantidade_total(s) == 3
    assert s["carrinho"] == {"1": 3}  # chaves viram texto (a sessão é JSON)


@pytest.mark.parametrize("p", [produto(estoque=0), produto(ativo=False), produto(categoria_ativa=False), None])
def test_nao_adiciona_o_que_nao_esta_a_venda(p):
    s = Sessao()
    assert carrinho.adicionar(s, p) == ("indisponivel", 0)
    assert carrinho.ler(s) == {}


def test_definir_troca_remove_e_limita():
    s, p = Sessao(), produto(estoque=4)
    carrinho.adicionar(s, p, 1)
    assert carrinho.definir(s, p, 3) == ("ok", 3)
    assert carrinho.definir(s, p, 10) == ("limitado", 4)
    assert carrinho.definir(s, p, 0) == ("ok", 0)
    assert carrinho.ler(s) == {}


def test_definir_tira_do_carrinho_produto_que_ficou_indisponivel():
    s, p = Sessao(), produto()
    carrinho.adicionar(s, p, 2)
    p.ativo = False
    assert carrinho.definir(s, p, 2) == ("indisponivel", 0)
    assert carrinho.ler(s) == {}


def test_remover_e_limpar():
    s = Sessao()
    carrinho.adicionar(s, produto(1), 1)
    carrinho.adicionar(s, produto(2), 1)
    carrinho.remover(s, 1)
    carrinho.remover(s, 99)  # inexistente não dá erro
    assert carrinho.ler(s) == {2: 1}
    carrinho.limpar(s)
    assert carrinho.ler(s) == {}


# ---------- Rotas (precisam do banco) ----------

def prod(slug="caneca-azul"):
    return Product.query.filter_by(slug=slug).one()


def sessao_do(client):
    with client.session_transaction() as s:
        return dict(s.get("carrinho", {}))


def test_carrinho_comeca_vazio(client):
    html = client.get("/carrinho/").get_data(as_text=True)
    assert "vazio" in html


def test_pagina_do_produto_tem_botao_de_adicionar(client, catalogo):
    html = client.get("/loja/caneca-azul").get_data(as_text=True)
    assert f"/carrinho/adicionar/{prod().id}" in html


def test_visitante_adiciona_sem_login_e_ve_o_total(client, catalogo):
    r = client.post(f"/carrinho/adicionar/{prod().id}", data={"quantidade": "2"})
    assert r.status_code == 302 and r.headers["Location"].endswith("/carrinho/")
    html = client.get("/carrinho/").get_data(as_text=True)
    assert "Caneca azul" in html
    assert "R$ 110,00" in html  # 2 x R$ 55,00
    assert "Carrinho (2)" in client.get("/").get_data(as_text=True)


def test_preco_vem_do_banco_e_nao_do_formulario(client, catalogo):
    client.post(f"/carrinho/adicionar/{prod().id}", data={"quantidade": "1", "preco": "1", "preco_centavos": "1"})
    assert "R$ 55,00" in client.get("/carrinho/").get_data(as_text=True)


@pytest.mark.parametrize("qtd", ["0", "-1", "abc", "1,5", "100"])
def test_quantidade_invalida_nao_entra(client, catalogo, qtd):
    client.post(f"/carrinho/adicionar/{prod().id}", data={"quantidade": qtd})
    assert sessao_do(client) == {}


def test_nao_passa_do_estoque(client, catalogo):
    pid = prod().id  # estoque 3
    client.post(f"/carrinho/adicionar/{pid}", data={"quantidade": "10"})
    assert sessao_do(client) == {str(pid): 3}


def test_produto_desativado_nao_entra(client, catalogo):
    client.post(f"/carrinho/adicionar/{prod('caneca-oculta').id}", data={"quantidade": "1"})
    assert sessao_do(client) == {}
    assert client.post("/carrinho/adicionar/99999", data={"quantidade": "1"}).status_code == 404


def test_atualizar_remover_e_esvaziar(client, catalogo):
    pid = prod().id
    client.post(f"/carrinho/adicionar/{pid}", data={"quantidade": "1"})
    client.post(f"/carrinho/atualizar/{pid}", data={"quantidade": "3"})
    assert sessao_do(client) == {str(pid): 3}
    client.post(f"/carrinho/atualizar/{pid}", data={"quantidade": "0"})
    assert sessao_do(client) == {}

    client.post(f"/carrinho/adicionar/{pid}", data={"quantidade": "1"})
    client.post(f"/carrinho/remover/{pid}")
    assert sessao_do(client) == {}

    client.post(f"/carrinho/adicionar/{pid}", data={"quantidade": "1"})
    client.post("/carrinho/limpar")
    assert sessao_do(client) == {}


def test_produto_que_sumiu_sai_do_carrinho_com_aviso(client, catalogo, app):
    from app.extensions import db

    pid = prod().id
    client.post(f"/carrinho/adicionar/{pid}", data={"quantidade": "2"})
    prod().ativo = False
    db.session.commit()
    html = client.get("/carrinho/").get_data(as_text=True)
    assert "não está mais disponível" in html
    assert sessao_do(client) == {}


def test_estoque_que_caiu_ajusta_a_quantidade(client, catalogo):
    from app.extensions import db

    pid = prod().id
    client.post(f"/carrinho/adicionar/{pid}", data={"quantidade": "3"})
    prod().estoque = 1
    db.session.commit()
    html = client.get("/carrinho/").get_data(as_text=True)
    assert "só temos 1" in html
    assert sessao_do(client) == {str(pid): 1}


def test_carrinhos_de_visitantes_sao_separados(app, catalogo):
    pid = prod().id
    um, outro = app.test_client(), app.test_client()
    um.post(f"/carrinho/adicionar/{pid}", data={"quantidade": "2"})
    assert sessao_do(outro) == {}


def test_sessao_adulterada_nao_quebra_a_pagina(client, catalogo):
    with client.session_transaction() as s:
        s["carrinho"] = {"abc": 2, "99999": 1, "1": "x"}
    assert client.get("/carrinho/").status_code == 200
