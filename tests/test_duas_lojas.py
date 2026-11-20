"""Duas lojas (peças e produtos para cerâmica), com busca e filtro dentro de cada uma."""
import re

import pytest
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import LOJA_PECAS, LOJA_PRODUTOS, Category, Product


@pytest.fixture()
def lojas(app):
    canecas = Category(nome="Canecas", slug="canecas")
    vasos = Category(nome="Vasos", slug="vasos", loja=LOJA_PECAS)
    tintas = Category(nome="Tintas", slug="tintas", loja=LOJA_PRODUTOS)
    argilas = Category(nome="Argilas", slug="argilas", loja=LOJA_PRODUTOS)
    oculta = Category(nome="Oculta", slug="oculta", loja=LOJA_PRODUTOS, ativa=False)
    db.session.add_all([
        Product(nome="Caneca Cerâmica Azul", slug="caneca-azul", preco_centavos=5500, estoque=3, categoria=canecas,
                descricao="Feita no torno"),
        Product(nome="Vaso Lótus", slug="vaso-lotus", preco_centavos=9000, estoque=1, categoria=vasos),
        Product(nome="Tinta azul", slug="tinta-azul", preco_centavos=3000, estoque=9, categoria=tintas,
                descricao="Corante para esmalte"),
        Product(nome="Argila branca", slug="argila-branca", preco_centavos=4000, estoque=9, categoria=argilas),
        Product(nome="Pincel escondido", slug="pincel", preco_centavos=1000, estoque=9, categoria=oculta),
        Product(nome="Tinta inativa", slug="tinta-inativa", preco_centavos=1000, estoque=9, categoria=tintas,
                ativo=False),
    ])
    db.session.commit()


def pagina(client, url):
    resposta = client.get(url)
    assert resposta.status_code == 200, url
    return resposta.get_data(as_text=True)


# ---------- Modelo ----------

def test_categoria_nova_fica_na_loja_de_pecas_por_padrao(app):
    categoria = Category(nome="Pratos", slug="pratos")
    db.session.add(categoria)
    db.session.commit()
    assert categoria.loja == LOJA_PECAS


def test_banco_recusa_loja_desconhecida(app):
    db.session.add(Category(nome="Outra", slug="outra", loja="outra"))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


# ---------- Escolha da loja ----------

def test_loja_abre_nas_pecas(client, lojas):
    html = pagina(client, "/loja/")
    assert "Caneca Cerâmica Azul" in html and "Vaso Lótus" in html
    assert "Tinta azul" not in html and "Argila branca" not in html


def test_loja_de_produtos_mostra_so_produtos_ativos(client, lojas):
    html = pagina(client, "/loja/?loja=produtos")
    assert "Tinta azul" in html and "Argila branca" in html
    assert "Caneca Cerâmica Azul" not in html
    assert "Tinta inativa" not in html and "Pincel escondido" not in html


def test_loja_desconhecida_da_404(client, lojas):
    assert client.get("/loja/?loja=outra").status_code == 404


def test_abas_ficam_no_topo_e_marcam_a_loja_atual(client, lojas):
    html = pagina(client, "/loja/?loja=produtos")
    abas = re.search(r'<nav class="abas-loja".*?</nav>', html, re.S).group(0)
    assert html.index('class="abas-loja"') < html.index("<h1")
    assert 'href="/loja/"' in abas
    assert 'href="/loja/?loja=produtos" aria-current="page"' in abas


# ---------- Filtro ----------

def test_filtro_lista_so_categorias_ativas_da_loja(client, lojas):
    html = pagina(client, "/loja/?loja=produtos")
    filtro = re.search(r'<nav class="filtro".*?</nav>', html, re.S).group(0)
    assert "Tintas" in filtro and "Argilas" in filtro
    assert "Canecas" not in filtro and "Oculta" not in filtro


def test_categoria_define_a_loja(client, lojas):
    html = pagina(client, "/loja/?categoria=tintas")
    assert "Tinta azul" in html and "Argila branca" not in html
    abas = re.search(r'<nav class="abas-loja".*?</nav>', html, re.S).group(0)
    assert 'href="/loja/?loja=produtos" aria-current="page"' in abas


def test_categoria_inativa_ou_inexistente_da_404(client, lojas):
    assert client.get("/loja/?categoria=oculta").status_code == 404
    assert client.get("/loja/?categoria=nada").status_code == 404


def test_tela_tem_lupa_e_icone_de_filtro(client, lojas):
    html = pagina(client, "/loja/?loja=produtos")
    busca = re.search(r'<form class="busca".*?</form>', html, re.S).group(0)
    assert 'role="search"' in busca and 'type="search"' in busca and 'name="q"' in busca
    assert 'name="loja" value="produtos"' in busca
    assert 'aria-label="Buscar"' in busca
    assert '<details class="filtro-loja"' in html and "<svg" in html[html.index("filtro-loja"):]


# ---------- Busca ----------

@pytest.mark.parametrize("termo", ["ceramica", "CERÂMICA", "torno", "azul caneca", "canecas"])
def test_busca_ignora_acento_e_maiuscula_e_olha_nome_descricao_e_categoria(client, lojas, termo):
    html = pagina(client, f"/loja/?q={termo}")
    assert "Caneca Cerâmica Azul" in html and "Vaso Lótus" not in html


def test_busca_fica_dentro_da_loja(client, lojas):
    assert "Tinta azul" not in pagina(client, "/loja/?q=azul")
    html = pagina(client, "/loja/?loja=produtos&q=azul")
    assert "Tinta azul" in html and "Caneca Cerâmica Azul" not in html


def test_busca_combina_com_a_categoria(client, lojas):
    assert "Tinta azul" not in pagina(client, "/loja/?categoria=argilas&q=azul")
    assert "Argila branca" in pagina(client, "/loja/?categoria=argilas&q=branca")


def test_filtro_mantem_a_busca_e_a_busca_mantem_o_filtro(client, lojas):
    html = pagina(client, "/loja/?loja=produtos&categoria=tintas&q=azul")
    assert 'href="/loja/?loja=produtos&amp;categoria=argilas&amp;q=azul"' in html
    busca = re.search(r'<form class="busca".*?</form>', html, re.S).group(0)
    assert 'name="categoria" value="tintas"' in busca and 'value="azul"' in busca


def test_busca_sem_resultado_avisa(client, lojas):
    html = pagina(client, "/loja/?q=inexistente")
    assert "Nada encontrado" in html and "inexistente" in html


def test_busca_vazia_mostra_tudo_e_coringa_nao_vale(client, lojas):
    assert "Vaso Lótus" in pagina(client, "/loja/?q=%20%20")
    assert "Nada encontrado" in pagina(client, "/loja/?q=%25")


def test_busca_escapa_o_texto_e_limita_o_tamanho(client, lojas):
    html = pagina(client, "/loja/?q=<script>alert(1)</script>")
    assert "<script>alert(1)" not in html
    longo = pagina(client, "/loja/?q=" + "a" * 500)
    busca = re.search(r'<form class="busca".*?</form>', longo, re.S).group(0)
    assert f'value="{"a" * 80}"' in busca


# ---------- Início e menu ----------

def test_inicio_separa_pecas_e_produtos(client, lojas):
    html = pagina(client, "/")
    saidas = html[html.index('id="saidas-do-forno"'):html.index('id="sobre"')]
    produtos = html[html.index('id="produtos"'):html.index("</main>")]
    assert "Caneca Cerâmica Azul" in saidas and "Tinta azul" not in saidas
    assert "Tinta azul" in produtos and "Caneca Cerâmica Azul" not in produtos
    assert 'class="faixa-produtos"' in produtos and "ceramistas" in produtos


def test_inicio_limita_as_faixas_a_oito_itens(client, lojas):
    categoria = Category.query.filter_by(slug="vasos").one()
    db.session.add_all([Product(nome=f"Vaso {n}", slug=f"vaso-{n}", preco_centavos=100, estoque=1, categoria=categoria)
                        for n in range(12)])
    db.session.commit()
    html = pagina(client, "/")
    saidas = html[html.index('id="saidas-do-forno"'):html.index('id="sobre"')]
    assert saidas.count('class="cartao"') == 8


def test_atalhos_do_inicio_sao_so_de_pecas(client, lojas):
    html = pagina(client, "/")
    atalhos = re.search(r'<ul class="atalhos".*?</ul>', html, re.S).group(0)
    assert "Canecas" in atalhos and "Tintas" not in atalhos


def test_carrossel_leva_cada_foto_para_a_sua_loja(client, lojas):
    html = pagina(client, "/")
    assert re.search(r'botao--ambar" href="/loja/">Ver as peças', html)
    assert re.search(r'botao--ambar" href="/loja/\?loja=produtos">Ver os produtos', html)


@pytest.mark.parametrize("url, marcado", [
    ("/loja/", 'href="/loja/" aria-current="page">Loja'),
    ("/loja/?loja=produtos", 'href="/loja/?loja=produtos" aria-current="page">Produtos'),
    ("/loja/?categoria=tintas", 'href="/loja/?loja=produtos" aria-current="page">Produtos'),
])
def test_menu_tem_as_duas_lojas(client, lojas, url, marcado):
    menu = re.search(r'id="menu-principal".*?</nav>', pagina(client, url), re.S).group(0)
    assert marcado in menu


def test_detalhe_marca_a_loja_do_produto_no_menu(client_cliente, lojas):
    menu = re.search(r'id="menu-principal".*?</nav>', pagina(client_cliente, "/loja/tinta-azul"), re.S).group(0)
    assert 'href="/loja/?loja=produtos" aria-current="page">Produtos' in menu


# ---------- Abas que saíram do menu ----------

@pytest.mark.parametrize("antiga, nova", [
    ("/contato", "/sobre#contato"),
    ("/pecas-personalizadas", "/servicos#personalizadas"),
])
def test_enderecos_antigos_redirecionam(client, antiga, nova):
    resposta = client.get(antiga)
    assert resposta.status_code == 301 and resposta.headers["Location"] == nova


# ---------- Painel ----------

def test_painel_cria_categoria_na_loja_escolhida(client_admin):
    r = client_admin.post("/admin/categorias/nova", data={"nome": "Esmaltes", "loja": "produtos", "ativa": "on"})
    assert r.status_code == 302
    assert Category.query.filter_by(nome="Esmaltes").one().loja == LOJA_PRODUTOS


def test_painel_muda_a_categoria_de_loja(client_admin, lojas):
    categoria = Category.query.filter_by(slug="vasos").one()
    r = client_admin.post(f"/admin/categorias/{categoria.id}/editar",
                          data={"nome": "Vasos", "loja": "produtos", "ativa": "on"})
    assert r.status_code == 302
    assert db.session.get(Category, categoria.id).loja == LOJA_PRODUTOS


def test_painel_recusa_loja_desconhecida(client_admin):
    r = client_admin.post("/admin/categorias/nova", data={"nome": "Esmaltes", "loja": "outra", "ativa": "on"})
    assert r.status_code == 200 and Category.query.filter_by(nome="Esmaltes").first() is None


def test_painel_mostra_a_loja_de_cada_categoria(client_admin, lojas):
    assert "Produtos para cerâmica" in pagina(client_admin, "/admin/categorias")
    assert 'name="loja"' in pagina(client_admin, "/admin/categorias/nova")


def test_cadastro_de_produto_agrupa_categorias_por_loja_e_pede_fotos(client_admin, lojas):
    html = pagina(client_admin, "/admin/produtos/novo")
    assert '<optgroup label="Peças de cerâmica">' in html
    assert '<optgroup label="Produtos para cerâmica">' in html
    assert "Fotos do produto" in html and 'name="imagens"' in html and "multiple" in html


# ---------- Demo ----------

def test_demo_preenche_as_duas_lojas(app):
    assert app.test_cli_runner().invoke(args=["seed-demo"]).exit_code == 0
    for loja in (LOJA_PECAS, LOJA_PRODUTOS):
        assert Product.query.join(Category).filter(Category.loja == loja).count() >= 3
