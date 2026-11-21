"""[back/painel-julia] A Julia cuida do site sozinha: capa e ordem das fotos, texto formatado,
destaque e ordem, serviços com foto e textos do site."""
import io
import os

import pytest

from app.extensions import db
from app.lojas import LOJA_PECAS
from app.models import Category, Course, CourseImage, Product, ProductImage, Service, TextoSite
from app.services.ordem import mover
from app.utils import sem_marcas, texto_destaque, texto_formatado

PNG = b"\x89PNG\r\n\x1a\n" + b"dados-da-imagem"


def foto(nome="foto.png"):
    return (io.BytesIO(PNG), nome)


def arquivos(app):
    pasta = os.path.join(app.config["UPLOAD_DIR"], "produtos")
    return sorted(os.listdir(pasta)) if os.path.isdir(pasta) else []


def produto_com_fotos(n=3, slug="caneca-azul"):
    produto = Product.query.filter_by(slug=slug).one()
    for i in range(n):
        produto.imagens.append(ProductImage(caminho=f"uploads/produtos/{slug}-{i}.png", ordem=i))
    db.session.commit()
    return produto


def ordem_dos_caminhos(imagens):
    return [imagem.caminho.rsplit("-", 1)[1] for imagem in imagens]


# ---------- Função de reordenar ----------

class Item:
    def __init__(self, nome):
        self.nome, self.ordem = nome, 0


@pytest.mark.parametrize("acao, alvo, esperado", [
    ("capa", "c", "cab"), ("antes", "b", "bac"), ("depois", "b", "acb"),
    ("antes", "a", "abc"), ("depois", "c", "abc"), ("qualquer", "b", "abc"),
])
def test_mover(acao, alvo, esperado):
    itens = [Item(n) for n in "abc"]
    resultado = mover(itens, next(i for i in itens if i.nome == alvo), acao)
    assert "".join(i.nome for i in resultado) == esperado
    assert [i.ordem for i in resultado] == [0, 1, 2]


# ---------- Fotos de produto ----------

def test_produto_usar_como_capa_e_setas(client_admin, catalogo):
    produto = produto_com_fotos()
    terceira = produto.imagens[2]
    url = f"/admin/produtos/{produto.id}/imagens/{terceira.id}/mover"
    assert client_admin.post(url, data={"acao": "capa"}).status_code == 302
    db.session.refresh(produto)
    assert ordem_dos_caminhos(produto.imagens) == ["2.png", "0.png", "1.png"]
    client_admin.post(url, data={"acao": "depois"})
    db.session.refresh(produto)
    assert ordem_dos_caminhos(produto.imagens) == ["0.png", "2.png", "1.png"]
    assert produto.imagem_principal.caminho.endswith("0.png")


def test_produto_mover_foto_de_outro_produto_da_404(client_admin, catalogo):
    produto = produto_com_fotos()
    outro = Product(nome="Outro", slug="outro", preco_centavos=100, estoque=1, categoria=produto.categoria)
    db.session.add(outro)
    db.session.commit()
    r = client_admin.post(f"/admin/produtos/{outro.id}/imagens/{produto.imagens[1].id}/mover", data={"acao": "capa"})
    assert r.status_code == 404


def test_produto_acao_invalida_da_400(client_admin, catalogo):
    produto = produto_com_fotos()
    r = client_admin.post(f"/admin/produtos/{produto.id}/imagens/{produto.imagens[1].id}/mover", data={"acao": "x"})
    assert r.status_code == 400


def test_formulario_do_produto_mostra_capa_e_setas(client_admin, catalogo):
    produto = produto_com_fotos()
    html = client_admin.get(f"/admin/produtos/{produto.id}/editar").get_data(as_text=True)
    assert html.count('value="capa"') == 2  # a capa atual não tem o botão
    assert "Mover a foto 2 para a esquerda" in html and "Mover a foto 3 para a direita" not in html
    assert ">Capa<" in html


def test_cliente_nao_mexe_nas_fotos(client_cliente, catalogo):
    produto = produto_com_fotos()
    r = client_cliente.post(f"/admin/produtos/{produto.id}/imagens/{produto.imagens[1].id}/mover", data={"acao": "capa"})
    assert r.status_code == 403


# ---------- Fotos de curso ----------

def curso_com_fotos(n=3):
    curso = Course(titulo="Torno", slug="torno")
    for i in range(n):
        curso.imagens.append(CourseImage(caminho=f"uploads/produtos/torno-{i}.png", ordem=i))
    db.session.add(curso)
    db.session.commit()
    return curso


def test_curso_escolhe_a_capa(client_admin):
    curso = curso_com_fotos()
    client_admin.post(f"/admin/cursos/{curso.id}/fotos/{curso.imagens[1].id}/mover", data={"acao": "capa"})
    db.session.refresh(curso)
    assert ordem_dos_caminhos(curso.imagens) == ["1.png", "0.png", "2.png"]


def test_curso_remover_a_capa_promove_a_proxima(client_admin):
    curso = curso_com_fotos()
    client_admin.post(f"/admin/cursos/{curso.id}/fotos/{curso.imagens[0].id}/excluir")
    db.session.refresh(curso)
    assert ordem_dos_caminhos(curso.imagens) == ["1.png", "2.png"]
    assert [i.ordem for i in curso.imagens] == [0, 1]


def test_curso_foto_de_outro_curso_da_404(client_admin):
    curso = curso_com_fotos()
    outro = Course(titulo="Outro", slug="outro")
    db.session.add(outro)
    db.session.commit()
    r = client_admin.post(f"/admin/cursos/{outro.id}/fotos/{curso.imagens[0].id}/mover", data={"acao": "capa"})
    assert r.status_code == 404
    assert client_admin.post(f"/admin/cursos/{outro.id}/fotos/{curso.imagens[0].id}/excluir").status_code == 404


def test_pagina_de_cursos_usa_a_capa_escolhida(client, client_admin):
    curso = curso_com_fotos()
    client_admin.post(f"/admin/cursos/{curso.id}/fotos/{curso.imagens[2].id}/mover", data={"acao": "capa"})
    html = client.get("/cursos").get_data(as_text=True)
    assert html.index("torno-2.png") < html.index("torno-0.png")


# ---------- Texto formatado ----------

def test_texto_formatado_paragrafos_lista_e_marcas():
    html = str(texto_formatado("Linha um\nlinha dois\n\n- item **forte**\n- item *leve*\n\nFim"))
    assert html == ("<p>Linha um<br>linha dois</p><ul><li>item <strong>forte</strong></li>"
                    "<li>item <em>leve</em></li></ul><p>Fim</p>")


@pytest.mark.parametrize("perigoso", ["<script>alert(1)</script>", '<img src=x onerror="alert(1)">',
                                      "**<b>x</b>**", "- <a href='javascript:x'>y</a>"])
def test_texto_formatado_nao_deixa_passar_html(perigoso):
    html = str(texto_formatado(perigoso))
    assert "<script" not in html and "<img" not in html and "<a " not in html and "<b>" not in html


def test_asterisco_de_conta_nao_vira_destaque():
    assert str(texto_formatado("2*3 = 6 e 4*5")) == "<p>2*3 = 6 e 4*5</p>"
    assert sem_marcas("Um *espaço* para **todos**") == "Um espaço para todos"
    assert str(texto_destaque("Um *espaço*")) == "Um <em>espaço</em>"


def test_pagina_do_produto_mostra_a_lista(client, catalogo):
    produto = Product.query.filter_by(slug="caneca-azul").one()
    produto.descricao = "Caneca feita à mão.\n\n- 300 ml\n- Vai ao micro-ondas"
    db.session.commit()
    html = client.get("/loja/caneca-azul").get_data(as_text=True)
    assert "<ul><li>300 ml</li><li>Vai ao micro-ondas</li></ul>" in html


# ---------- Destaque e ordem ----------

def dados_produto(categoria_id, **extra):
    return {"nome": "Caneca azul", "preco": "55,00", "estoque": "3", "categoria_id": str(categoria_id),
            "descricao": "", "ativo": "on", "peso_gramas": "400", "altura_cm": "12", "largura_cm": "10",
            "comprimento_cm": "10", **extra}


def test_painel_marca_e_desmarca_destaque(client_admin, catalogo):
    produto = Product.query.filter_by(slug="caneca-azul").one()
    client_admin.post(f"/admin/produtos/{produto.id}/editar", data=dados_produto(produto.categoria_id, destaque="on"))
    db.session.refresh(produto)
    assert produto.destaque is True
    assert "Destaque</span>" in client_admin.get("/admin/produtos").get_data(as_text=True)
    client_admin.post(f"/admin/produtos/{produto.id}/editar", data=dados_produto(produto.categoria_id))
    db.session.refresh(produto)
    assert produto.destaque is False


def test_destaque_vem_primeiro_na_inicio_e_na_loja(client, app):
    pecas = Category(nome="Vasos", slug="vasos", loja=LOJA_PECAS)
    db.session.add(pecas)
    for nome in ("Antigo destacado", "Novo comum"):
        db.session.add(Product(nome=nome, slug=nome.lower().replace(" ", "-"), preco_centavos=100, estoque=1,
                               categoria=pecas, destaque=nome.startswith("Antigo")))
    db.session.commit()
    for url in ("/", "/loja/"):
        html = client.get(url).get_data(as_text=True)
        assert html.index("Antigo destacado") < html.index("Novo comum"), url


def test_curso_com_posicao(client, client_admin):
    for titulo, ordem in (("A primeiro alfabeto", "2"), ("Z primeiro na página", "1")):
        client_admin.post("/admin/cursos/novo", data={"titulo": titulo, "descricao": "", "ordem": ordem, "ativo": "on"},
                          content_type="multipart/form-data")
    html = client.get("/cursos").get_data(as_text=True)
    assert html.index("Z primeiro na página") < html.index("A primeiro alfabeto")
    assert Course.query.filter_by(titulo="Z primeiro na página").one().ordem == 1


def test_posicao_invalida_avisa(client_admin):
    r = client_admin.post("/admin/cursos/novo", data={"titulo": "X", "ordem": "-3", "ativo": "on"},
                          content_type="multipart/form-data", follow_redirects=True)
    assert "Posição: use um número inteiro" in r.get_data(as_text=True)
    assert Course.query.count() == 0


# ---------- Serviços com foto e ordem ----------

def enviar_servico(client, url, **campos):
    base = {"titulo": "Queima de peças", "descricao": "Forno a gás", "ativo": "on"}
    return client.post(url, data={**base, **campos}, content_type="multipart/form-data")


def test_servico_com_foto_aparece_no_site(app, client, client_admin):
    assert enviar_servico(client_admin, "/admin/servicos/novo", foto=foto(), ordem="2").status_code == 302
    servico = Service.query.one()
    assert servico.foto.startswith("uploads/") and servico.ordem == 2 and len(arquivos(app)) == 1
    html = client.get("/servicos").get_data(as_text=True)
    assert servico.foto in html and 'class="servico__foto"' in html


def test_trocar_e_remover_foto_do_servico_apaga_o_arquivo(app, client_admin):
    enviar_servico(client_admin, "/admin/servicos/novo", foto=foto())
    servico = Service.query.one()
    antiga = servico.foto
    enviar_servico(client_admin, f"/admin/servicos/{servico.id}/editar", foto=foto("nova.png"))
    db.session.refresh(servico)
    assert servico.foto != antiga and len(arquivos(app)) == 1
    enviar_servico(client_admin, f"/admin/servicos/{servico.id}/editar", remover_foto="on")
    db.session.refresh(servico)
    assert servico.foto == "" and arquivos(app) == []


def test_excluir_servico_apaga_a_foto(app, client_admin):
    enviar_servico(client_admin, "/admin/servicos/novo", foto=foto())
    servico = Service.query.one()
    client_admin.post(f"/admin/servicos/{servico.id}/excluir")
    assert Service.query.count() == 0 and arquivos(app) == []


def test_foto_invalida_nao_cria_servico(app, client_admin):
    r = enviar_servico(client_admin, "/admin/servicos/novo", foto=(io.BytesIO(b"<html>"), "x.png"))
    assert r.status_code == 200 and Service.query.count() == 0 and arquivos(app) == []


def test_servicos_na_ordem_escolhida(client, client_admin):
    enviar_servico(client_admin, "/admin/servicos/novo", titulo="A segundo", ordem="2")
    enviar_servico(client_admin, "/admin/servicos/novo", titulo="Z primeiro", ordem="1")
    html = client.get("/servicos").get_data(as_text=True)
    assert html.index("Z primeiro") < html.index("A segundo")


# ---------- Textos do site ----------

def test_sem_mudanca_o_site_usa_o_texto_original(client):
    assert "Um espaço para aprender, <em>criar e viver a cerâmica.</em>" in client.get("/").get_data(as_text=True)
    assert "Conte sua ideia" in client.get("/servicos").get_data(as_text=True)


def test_julia_muda_o_slogan_e_os_passos(client, client_admin):
    r = client_admin.post("/admin/textos", data={"slogan": "Cerâmica feita *com calma.*",
                                                 "passo1_titulo": "Mande uma foto"}, follow_redirects=True)
    assert "Textos salvos" in r.get_data(as_text=True)
    inicio = client.get("/").get_data(as_text=True)
    assert "Cerâmica feita <em>com calma.</em>" in inicio and "<title>Malosti Arte Cerâmica · Cerâmica feita com calma</title>" in inicio
    assert "Mande uma foto" in client.get("/servicos").get_data(as_text=True)
    assert "Malosti Arte Cerâmica. Cerâmica feita com calma." in client.get("/sobre").get_data(as_text=True)


def test_campo_vazio_volta_ao_original_e_nao_guarda_nada(client_admin):
    client_admin.post("/admin/textos", data={"slogan": "Outro slogan"})
    assert TextoSite.query.count() == 1
    client_admin.post("/admin/textos", data={"slogan": ""})
    assert TextoSite.query.count() == 0


def test_texto_do_sobre_aceita_paragrafos_e_escapa_html(client, client_admin):
    client_admin.post("/admin/textos", data={"sobre_texto": "Primeiro.\n\nSegundo <script>x</script>"})
    html = client.get("/sobre").get_data(as_text=True)
    assert "<p>Primeiro.</p><p>Segundo &lt;script&gt;x&lt;/script&gt;</p>" in html


def test_texto_longo_demais_nao_salva(client_admin):
    r = client_admin.post("/admin/textos", data={"slogan": "x" * 121}, follow_redirects=True)
    assert "use no máximo 120 caracteres" in r.get_data(as_text=True)
    assert TextoSite.query.count() == 0


def test_textos_do_site_so_para_admin(client, client_cliente):
    assert client_cliente.get("/admin/textos").status_code == 403
    assert client_cliente.post("/admin/textos", data={"slogan": "invadido"}).status_code == 403
    assert TextoSite.query.count() == 0


def test_menu_do_painel_tem_textos_do_site(client_admin):
    assert 'href="/admin/textos"' in client_admin.get("/admin/").get_data(as_text=True)
