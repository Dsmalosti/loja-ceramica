import io
import os

import pytest

from app.extensions import db
from app.models import Category, Course, Product, ProductImage, Service

PNG = b"\x89PNG\r\n\x1a\n" + b"dados-da-imagem"


def foto(nome="foto.png", conteudo=PNG):
    return (io.BytesIO(conteudo), nome)


def multipart(**campos):
    return {"data": campos, "content_type": "multipart/form-data"}


def pasta_uploads(app):
    return os.path.join(app.config["UPLOAD_DIR"], "produtos")


def arquivos(app):
    pasta = pasta_uploads(app)
    return os.listdir(pasta) if os.path.isdir(pasta) else []


# ---------- Acesso ----------

ROTAS_GET = [
    "/admin/categorias", "/admin/categorias/nova",
    "/admin/produtos", "/admin/produtos/novo",
    "/admin/cursos", "/admin/cursos/novo",
    "/admin/servicos", "/admin/servicos/novo",
]


@pytest.mark.parametrize("url", ROTAS_GET)
def test_visitante_vai_para_o_login(client, url):
    resposta = client.get(url)
    assert resposta.status_code == 302
    assert "/entrar" in resposta.headers["Location"]


@pytest.mark.parametrize("url", ROTAS_GET)
def test_cliente_comum_recebe_403(client, criar_usuario, url):
    criar_usuario()
    client.post("/entrar", data={"email": "cliente@exemplo.com", "senha": "senha-segura-123"})
    assert client.get(url).status_code == 403


def test_visitante_nao_consegue_agir_por_post(client, catalogo):
    produto = Product.query.filter_by(slug="caneca-azul").one()
    for url in (f"/admin/produtos/{produto.id}/excluir", f"/admin/produtos/{produto.id}/alternar"):
        assert client.post(url).status_code == 302
    assert db.session.get(Product, produto.id) is not None


@pytest.mark.parametrize("url", ROTAS_GET)
def test_admin_abre_as_telas(client_admin, catalogo, url):
    assert client_admin.get(url).status_code == 200


def test_dashboard_tem_atalhos(client_admin):
    html = client_admin.get("/admin/").get_data(as_text=True)
    for destino in ("/admin/produtos", "/admin/categorias", "/admin/cursos", "/admin/servicos"):
        assert destino in html


# ---------- Categorias ----------

def test_categoria_criar_editar_alternar_excluir(client_admin):
    r = client_admin.post("/admin/categorias/nova", data={"nome": "Pratos", "ativa": "on"})
    assert r.status_code == 302
    cat = Category.query.filter_by(nome="Pratos").one()
    assert cat.slug == "pratos" and cat.ativa

    client_admin.post(f"/admin/categorias/{cat.id}/editar", data={"nome": "Pratos fundos", "ativa": "on"})
    db.session.refresh(cat)
    assert cat.nome == "Pratos fundos"
    assert cat.slug == "pratos"  # slug não muda ao renomear (links continuam valendo)

    client_admin.post(f"/admin/categorias/{cat.id}/alternar")
    db.session.refresh(cat)
    assert cat.ativa is False

    client_admin.post(f"/admin/categorias/{cat.id}/excluir")
    assert db.session.get(Category, cat.id) is None


def test_categoria_nome_repetido_ou_vazio_e_recusado(client_admin, catalogo):
    r = client_admin.post("/admin/categorias/nova", data={"nome": "  canecas ", "ativa": "on"})
    assert r.status_code == 200
    assert Category.query.count() == 1
    assert client_admin.post("/admin/categorias/nova", data={"nome": ""}).status_code == 200


def test_categoria_com_produtos_nao_pode_ser_excluida(client_admin, catalogo):
    cat = Category.query.filter_by(slug="canecas").one()
    client_admin.post(f"/admin/categorias/{cat.id}/excluir")
    assert db.session.get(Category, cat.id) is not None


def test_categoria_inexistente_da_404(client_admin):
    assert client_admin.get("/admin/categorias/999/editar").status_code == 404
    assert client_admin.post("/admin/categorias/999/excluir").status_code == 404


# ---------- Produtos ----------

def dados_produto(cat_id, **extra):
    base = {"nome": "Vaso grande", "categoria_id": str(cat_id), "preco": "120,50",
            "estoque": "2", "descricao": "Vaso feito à mão", "ativo": "on"}
    base.update(extra)
    return base


def test_produto_criar_sem_foto(client_admin, catalogo):
    cat = Category.query.filter_by(slug="canecas").one()
    r = client_admin.post("/admin/produtos/novo", **multipart(**dados_produto(cat.id)))
    assert r.status_code == 302
    produto = Product.query.filter_by(slug="vaso-grande").one()
    assert produto.preco_centavos == 12050 and produto.estoque == 2 and produto.ativo


def test_slug_de_produto_repetido_ganha_sufixo(client_admin, catalogo):
    cat = Category.query.filter_by(slug="canecas").one()
    for _ in range(2):
        client_admin.post("/admin/produtos/novo", **multipart(**dados_produto(cat.id, nome="Prato fundo")))
    slugs = sorted(p.slug for p in Product.query.filter(Product.nome == "Prato fundo"))
    assert slugs == ["prato-fundo", "prato-fundo-2"]


@pytest.mark.parametrize("campo, valor", [("preco", "abc"), ("preco", "0"), ("estoque", "-1"), ("nome", " ")])
def test_produto_invalido_nao_grava_e_reexibe_o_formulario(client_admin, catalogo, campo, valor):
    cat = Category.query.filter_by(slug="canecas").one()
    antes = Product.query.count()
    r = client_admin.post("/admin/produtos/novo", **multipart(**dados_produto(cat.id, **{campo: valor})))
    assert r.status_code == 200
    assert Product.query.count() == antes


def test_produto_com_categoria_inexistente_e_recusado(client_admin, catalogo):
    antes = Product.query.count()
    r = client_admin.post("/admin/produtos/novo", **multipart(**dados_produto(9999)))
    assert r.status_code == 200 and Product.query.count() == antes


def test_produto_editar_mantem_slug_e_nao_mexe_nas_fotos(client_admin, catalogo):
    produto = Product.query.filter_by(slug="caneca-azul").one()
    client_admin.post(f"/admin/produtos/{produto.id}/editar",
                      **multipart(**dados_produto(produto.categoria_id, nome="Caneca azul-petróleo", preco="60")))
    db.session.refresh(produto)
    assert produto.nome == "Caneca azul-petróleo"
    assert produto.slug == "caneca-azul"
    assert produto.preco_centavos == 6000


def test_produto_alternar_controla_a_vitrine(client_admin, catalogo):
    produto = Product.query.filter_by(slug="caneca-azul").one()
    assert "Caneca azul" in client_admin.get("/loja/").get_data(as_text=True)

    client_admin.post(f"/admin/produtos/{produto.id}/alternar", follow_redirects=True)
    assert "Caneca azul" not in client_admin.get("/loja/").get_data(as_text=True)
    assert client_admin.get("/loja/caneca-azul").status_code == 404

    client_admin.post(f"/admin/produtos/{produto.id}/alternar", follow_redirects=True)
    assert client_admin.get("/loja/caneca-azul").status_code == 200


def test_produto_excluir(client_admin, catalogo):
    produto = Product.query.filter_by(slug="caneca-oculta").one()
    client_admin.post(f"/admin/produtos/{produto.id}/excluir")
    assert db.session.get(Product, produto.id) is None


def test_filtros_da_lista(client_admin, catalogo):
    html = client_admin.get("/admin/produtos?status=inativos").get_data(as_text=True)
    assert "Caneca oculta" in html and "Caneca azul" not in html
    html = client_admin.get("/admin/produtos?q=azul").get_data(as_text=True)
    assert "Caneca azul" in html and "Caneca oculta" not in html
    # caracteres especiais do LIKE não podem quebrar nem listar tudo
    html = client_admin.get("/admin/produtos?q=%25").get_data(as_text=True)
    assert "Caneca azul" not in html


# ---------- Fotos ----------

def test_produto_novo_com_fotos(app, client_admin, catalogo):
    cat = Category.query.filter_by(slug="canecas").one()
    r = client_admin.post("/admin/produtos/novo",
                          **multipart(**dados_produto(cat.id), imagens=[foto("a.png"), foto("b.png")]))
    assert r.status_code == 302
    produto = Product.query.filter_by(slug="vaso-grande").one()
    assert [i.ordem for i in produto.imagens] == [0, 1]
    assert len(arquivos(app)) == 2


def test_foto_falsa_recusa_o_produto_inteiro_e_nao_deixa_lixo(app, client_admin, catalogo):
    cat = Category.query.filter_by(slug="canecas").one()
    antes = Product.query.count()
    r = client_admin.post("/admin/produtos/novo", **multipart(
        **dados_produto(cat.id), imagens=[foto("ok.png"), foto("virus.png", b"<script>x</script>")]))
    assert r.status_code == 200
    assert Product.query.count() == antes
    assert arquivos(app) == []


def test_adicionar_remover_e_trocar_principal(app, client_admin, catalogo):
    produto = Product.query.filter_by(slug="caneca-azul").one()
    client_admin.post(f"/admin/produtos/{produto.id}/imagens",
                      **multipart(imagens=[foto("1.png"), foto("2.png")]))
    db.session.refresh(produto)
    primeira, segunda = produto.imagens
    assert len(arquivos(app)) == 2

    client_admin.post(f"/admin/produtos/{produto.id}/imagens/{segunda.id}/principal")
    db.session.refresh(produto)
    assert produto.imagens[0].id == segunda.id

    client_admin.post(f"/admin/produtos/{produto.id}/imagens/{primeira.id}/excluir")
    db.session.refresh(produto)
    assert [i.id for i in produto.imagens] == [segunda.id]
    assert len(arquivos(app)) == 1


def test_limite_de_8_fotos(app, client_admin, catalogo):
    produto = Product.query.filter_by(slug="caneca-azul").one()
    client_admin.post(f"/admin/produtos/{produto.id}/imagens",
                      **multipart(imagens=[foto(f"{i}.png") for i in range(8)]))
    client_admin.post(f"/admin/produtos/{produto.id}/imagens", **multipart(imagens=[foto("extra.png")]))
    assert ProductImage.query.filter_by(produto_id=produto.id).count() == 8
    assert len(arquivos(app)) == 8


def test_foto_de_outro_produto_nao_pode_ser_mexida(app, client_admin, catalogo):
    a = Product.query.filter_by(slug="caneca-azul").one()
    b = Product.query.filter_by(slug="caneca-oculta").one()
    client_admin.post(f"/admin/produtos/{a.id}/imagens", **multipart(imagens=[foto()]))
    imagem = ProductImage.query.filter_by(produto_id=a.id).one()
    assert client_admin.post(f"/admin/produtos/{b.id}/imagens/{imagem.id}/excluir").status_code == 404
    assert db.session.get(ProductImage, imagem.id) is not None


def test_excluir_produto_apaga_os_arquivos(app, client_admin, catalogo):
    produto = Product.query.filter_by(slug="caneca-azul").one()
    client_admin.post(f"/admin/produtos/{produto.id}/imagens", **multipart(imagens=[foto(), foto("2.png")]))
    assert len(arquivos(app)) == 2
    client_admin.post(f"/admin/produtos/{produto.id}/excluir")
    assert arquivos(app) == []
    assert ProductImage.query.count() == 0


def test_arquivo_grande_demais_mostra_pagina_amigavel(app, client_admin, catalogo):
    app.config["MAX_CONTENT_LENGTH"] = 1024
    produto = Product.query.filter_by(slug="caneca-azul").one()
    r = client_admin.post(f"/admin/produtos/{produto.id}/imagens",
                          **multipart(imagens=[foto("g.png", PNG + b"0" * 5000)]))
    assert r.status_code == 413
    assert "grande demais" in r.get_data(as_text=True).lower()


# ---------- Cursos e serviços ----------

def test_curso_crud_com_valor_opcional(client_admin):
    client_admin.post("/admin/cursos/novo", data={"titulo": "Torno básico", "duracao": "4 encontros", "ativo": "on"})
    curso = Course.query.filter_by(slug="torno-basico").one()
    assert curso.valor_centavos is None

    client_admin.post(f"/admin/cursos/{curso.id}/editar", data={"titulo": "Torno básico", "valor": "350", "ativo": "on"})
    db.session.refresh(curso)
    assert curso.valor_centavos == 35000

    assert "Torno básico" in client_admin.get("/cursos").get_data(as_text=True)
    client_admin.post(f"/admin/cursos/{curso.id}/alternar", follow_redirects=True)
    assert "Torno básico" not in client_admin.get("/cursos").get_data(as_text=True)

    client_admin.post(f"/admin/cursos/{curso.id}/excluir")
    assert db.session.get(Course, curso.id) is None


def test_curso_invalido(client_admin):
    assert client_admin.post("/admin/cursos/novo", data={"titulo": "X", "valor": "caro"}).status_code == 200
    assert Course.query.count() == 0


def test_servico_crud(client_admin):
    client_admin.post("/admin/servicos/novo", data={"titulo": "Queima de peças", "descricao": "Forno a 1000°C", "ativo": "on"})
    servico = Service.query.one()

    client_admin.post(f"/admin/servicos/{servico.id}/editar", data={"titulo": "Queima de peças", "descricao": "Novo texto", "ativo": "on"})
    db.session.refresh(servico)
    assert servico.descricao == "Novo texto"

    assert "Queima de peças" in client_admin.get("/servicos").get_data(as_text=True)
    client_admin.post(f"/admin/servicos/{servico.id}/alternar", follow_redirects=True)
    assert "Queima de peças" not in client_admin.get("/servicos").get_data(as_text=True)

    client_admin.post(f"/admin/servicos/{servico.id}/excluir")
    assert Service.query.count() == 0
