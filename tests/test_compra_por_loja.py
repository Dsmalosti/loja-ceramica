"""Compra por loja: peças pelo WhatsApp, produtos pelo site com retirada no ateliê."""
import pytest

from app.extensions import db
from app.models import LOJA_PECAS, LOJA_PRODUTOS, Category, Pedido, Product
from app.services import mercadopago

HORARIO = "Segunda a sexta, das 9h às 12h e das 14h às 17h"
ENVIO = {"peso_gramas": "250", "altura_cm": "10", "largura_cm": "8", "comprimento_cm": "6"}


@pytest.fixture()
def peca(app):
    categoria = Category(nome="Vasos", slug="vasos", loja=LOJA_PECAS)
    produto = Product(nome="Vaso Lótus", slug="vaso-lotus", preco_centavos=9000, estoque=1, categoria=categoria)
    db.session.add(produto)
    db.session.commit()
    return produto


@pytest.fixture()
def mp(monkeypatch):
    def falso(metodo, caminho, corpo=None, idempotencia=None):
        ref = corpo["external_reference"]
        return {"id": f"pref-{ref}", "init_point": f"https://mp.exemplo.test/?pref={ref}"}

    monkeypatch.setattr(mercadopago, "_requisicao", falso)


def produto_do_site():
    return Product.query.filter_by(slug="caneca-azul").one()


def carrinho_de(client):
    with client.session_transaction() as sessao:
        return dict(sessao.get("carrinho", {}))


def token_do_resumo(client):
    client.get("/checkout/")
    with client.session_transaction() as sessao:
        return sessao.get("checkout_token")


# ---------- Detalhe aberto ----------

def test_detalhe_abre_sem_login_nas_duas_lojas(client, catalogo, peca):
    assert client.get("/loja/caneca-azul").status_code == 200
    assert client.get("/loja/vaso-lotus").status_code == 200
    assert client.get("/loja/caneca-oculta").status_code == 404


def test_loja_nao_pede_login_para_ver_detalhes(client, catalogo, peca):
    assert "Entre na sua conta" not in client.get("/loja/").get_data(as_text=True)


# ---------- Peça: WhatsApp ----------

def test_peca_fecha_pelo_whatsapp_e_nao_tem_carrinho(client, peca):
    html = client.get("/loja/vaso-lotus").get_data(as_text=True)
    assert "Comprar pelo WhatsApp" in html and "wa.me/" in html
    assert "Vaso%20L%C3%B3tus" in html
    assert "/carrinho/adicionar" not in html and "Adicionar ao carrinho" not in html


def test_peca_sem_estoque_pode_ser_encomendada(client, peca):
    peca.estoque = 0
    db.session.commit()
    assert "Encomendar pelo WhatsApp" in client.get("/loja/vaso-lotus").get_data(as_text=True)


def test_peca_mostra_prazo_retirada_e_regras(client, peca):
    html = client.get("/loja/vaso-lotus").get_data(as_text=True)
    assert "30 a 40 dias" in html and HORARIO in html and "10 dias" in html
    assert "transportadora" in html and "outra peça" in html


def test_servidor_recusa_peca_no_carrinho(client_cliente, peca):
    r = client_cliente.post(f"/carrinho/adicionar/{peca.id}", data={"quantidade": "1"})
    assert r.status_code == 302 and r.headers["Location"] == "/loja/vaso-lotus"
    assert carrinho_de(client_cliente) == {}


def test_peca_que_ja_estava_na_sessao_sai_do_carrinho(client_cliente, peca):
    with client_cliente.session_transaction() as sessao:
        sessao["carrinho"] = {str(peca.id): 1}
    html = client_cliente.get("/carrinho/", follow_redirects=True).get_data(as_text=True)
    assert "não está mais disponível" in html and carrinho_de(client_cliente) == {}


def test_atualizar_nao_coloca_peca_no_carrinho(client_cliente, peca):
    client_cliente.post(f"/carrinho/atualizar/{peca.id}", data={"quantidade": "1"})
    assert carrinho_de(client_cliente) == {}


# ---------- Produto: site ----------

def test_produto_tem_carrinho_e_retirada(client, catalogo):
    html = client.get("/loja/caneca-azul").get_data(as_text=True)
    assert "Adicionar ao carrinho" in html and HORARIO in html and "10 dias" in html
    assert "Comprar pelo WhatsApp" not in html and "30 a 40 dias" not in html


def test_visitante_que_adiciona_produto_entra_e_volta_para_ele(client, catalogo):
    r = client.post(f"/carrinho/adicionar/{produto_do_site().id}", data={"quantidade": "1"})
    assert "/entrar" in r.headers["Location"] and "next=/loja/caneca-azul" in r.headers["Location"]


# ---------- Checkout: só retirada ----------

def test_resumo_oferece_so_a_retirada(client_cliente, catalogo, mp):
    client_cliente.post(f"/carrinho/adicionar/{produto_do_site().id}", data={"quantidade": "1"})
    html = client_cliente.get("/checkout/").get_data(as_text=True)
    assert "Retirada no ateliê" in html and HORARIO in html and "Rua Espanha, 532" in html
    assert "Receber em casa" not in html and 'name="entrega"' not in html and "Frete" not in html


def test_pedido_e_sempre_retirada_sem_frete(client_cliente, catalogo, mp):
    client_cliente.post(f"/carrinho/adicionar/{produto_do_site().id}", data={"quantidade": "2"})
    r = client_cliente.post("/checkout/confirmar", data={"token": token_do_resumo(client_cliente)})
    pedido = Pedido.query.one()
    assert r.status_code == 303
    assert pedido.entrega_tipo == "retirada" and pedido.frete_centavos == 0 and pedido.total_centavos == 11000


def test_servidor_recusa_entrega_em_casa(client_cliente, catalogo, mp):
    client_cliente.post(f"/carrinho/adicionar/{produto_do_site().id}", data={"quantidade": "1"})
    r = client_cliente.post("/checkout/confirmar", data={"token": token_do_resumo(client_cliente), "entrega": "entrega"})
    assert r.headers["Location"] == "/checkout/" and Pedido.query.count() == 0


def test_categoria_movida_para_pecas_barra_o_pedido(client_cliente, catalogo, mp):
    client_cliente.post(f"/carrinho/adicionar/{produto_do_site().id}", data={"quantidade": "1"})
    token = token_do_resumo(client_cliente)
    produto_do_site().categoria.loja = LOJA_PECAS
    db.session.commit()
    client_cliente.post("/checkout/confirmar", data={"token": token})
    assert Pedido.query.count() == 0


# ---------- Peso e medidas ----------

def form_produto(categoria, **extra):
    return {"nome": "Esmalte", "categoria_id": str(categoria.id), "preco": "30,00", "estoque": "4", "ativo": "on", **extra}


def test_cadastro_tem_campos_de_peso_e_medidas(client_admin, catalogo):
    html = client_admin.get("/admin/produtos/novo").get_data(as_text=True)
    for campo in ENVIO:
        assert f'name="{campo}"' in html


def test_produto_para_ceramica_exige_peso_e_medidas(client_admin, catalogo):
    categoria = Category.query.filter_by(slug="canecas").one()
    assert categoria.loja == LOJA_PRODUTOS
    r = client_admin.post("/admin/produtos/novo", data=form_produto(categoria, peso_gramas="250"))
    assert r.status_code == 200 and Product.query.filter_by(nome="Esmalte").first() is None


def test_produto_guarda_peso_e_medidas_e_edicao_mostra(client_admin, catalogo):
    categoria = Category.query.filter_by(slug="canecas").one()
    r = client_admin.post("/admin/produtos/novo", data=form_produto(categoria, **ENVIO))
    produto = Product.query.filter_by(nome="Esmalte").one()
    assert r.status_code == 302
    assert (produto.peso_gramas, produto.altura_cm, produto.largura_cm, produto.comprimento_cm) == (250, 10, 8, 6)
    assert 'name="peso_gramas" type="number" min="1" max="100000" step="1" value="250"' in \
        client_admin.get(f"/admin/produtos/{produto.id}/editar").get_data(as_text=True)


def test_peca_nao_exige_peso_e_medidas(client_admin, peca):
    r = client_admin.post("/admin/produtos/novo", data=form_produto(peca.categoria))
    assert r.status_code == 302 and Product.query.filter_by(nome="Esmalte").one().peso_gramas is None


@pytest.mark.parametrize("campo, valor", [("peso_gramas", "0"), ("altura_cm", "abc"), ("largura_cm", "-1"), ("comprimento_cm", "9999")])
def test_peso_e_medidas_invalidos_sao_recusados(client_admin, peca, campo, valor):
    r = client_admin.post("/admin/produtos/novo", data=form_produto(peca.categoria, **{**ENVIO, campo: valor}))
    assert r.status_code == 200 and Product.query.filter_by(nome="Esmalte").first() is None


# ---------- Demo ----------

def test_demo_vende_so_produtos_com_retirada_e_medidas(app):
    assert app.test_cli_runner().invoke(args=["seed-demo"]).exit_code == 0
    produtos = Product.query.join(Category).filter(Category.loja == LOJA_PRODUTOS).all()
    assert produtos and all(p.peso_gramas and p.altura_cm and p.largura_cm and p.comprimento_cm for p in produtos)
    assert all(p.entrega_tipo == "retirada" and p.frete_centavos == 0 for p in Pedido.query.all())
    assert all(item.produto.compra_pelo_site for p in Pedido.query.all() for item in p.itens)
