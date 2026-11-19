"""Cursos: turma aberta ou fechada, fotos do curso e quem ensina (nome, foto e Instagram)."""
import io
import os
import re

import pytest

from app.extensions import db
from app.models import Course, CourseImage

PNG = b"\x89PNG\r\n\x1a\n" + b"dados-da-imagem"


def foto(nome="foto.png", conteudo=PNG):
    return (io.BytesIO(conteudo), nome)


def enviar(client, url, **campos):
    base = {"titulo": "Torno básico", "duracao": "4 encontros", "valor": "300,00", "descricao": "Aulas", "ativo": "on"}
    return client.post(url, data={**base, **campos}, content_type="multipart/form-data")


def arquivos(app):
    pasta = os.path.join(app.config["UPLOAD_DIR"], "produtos")
    return sorted(os.listdir(pasta)) if os.path.isdir(pasta) else []


def curso():
    return Course.query.filter_by(titulo="Torno básico").one()


# ---------- Modelo ----------

def test_curso_novo_comeca_com_turma_aberta_e_sem_professor(app):
    novo = Course(titulo="X", slug="x")
    db.session.add(novo)
    db.session.commit()
    assert novo.turma_aberta is True and novo.professor_nome == "" and novo.imagens == []
    assert novo.instagram_url == ""


# ---------- Painel ----------

def test_painel_cria_curso_completo(app, client_admin):
    r = enviar(client_admin, "/admin/cursos/novo", turma="fechada", professor_nome="Ana Souza",
               professor_instagram="https://www.instagram.com/ana.ceramica/?hl=pt",
               professor_foto=foto("ana.png"), fotos=[foto("a.png"), foto("b.png")])
    assert r.status_code == 302
    c = curso()
    assert c.turma_aberta is False and c.professor_nome == "Ana Souza" and c.professor_instagram == "ana.ceramica"
    assert c.professor_foto.startswith("uploads/") and len(c.imagens) == 2
    assert [i.ordem for i in c.imagens] == [0, 1] and len(arquivos(app)) == 3


def test_painel_aceita_instagram_com_arroba(client_admin):
    enviar(client_admin, "/admin/cursos/novo", professor_instagram="@ana_ceramica")
    assert curso().professor_instagram == "ana_ceramica"


@pytest.mark.parametrize("instagram", ["ana ceramica", "https://evil.com/ana", "javascript:alert(1)", "a" * 31])
def test_painel_recusa_instagram_invalido(client_admin, instagram):
    r = enviar(client_admin, "/admin/cursos/novo", professor_instagram=instagram)
    assert r.status_code == 200 and Course.query.count() == 0


def test_painel_recusa_foto_que_nao_e_imagem_e_nao_grava_nada(app, client_admin):
    r = enviar(client_admin, "/admin/cursos/novo", fotos=[foto("a.png"), foto("b.png", b"<html>")])
    assert r.status_code == 200 and Course.query.count() == 0 and arquivos(app) == []


def test_painel_limita_a_quantidade_de_fotos(app, client_admin):
    r = enviar(client_admin, "/admin/cursos/novo", fotos=[foto(f"{n}.png") for n in range(7)])
    assert r.status_code == 200 and Course.query.count() == 0 and arquivos(app) == []


def test_formulario_antigo_sem_turma_fica_aberta(client_admin):
    client_admin.post("/admin/cursos/novo", data={"titulo": "Torno básico", "ativo": "on"})
    assert curso().turma_aberta is True


def test_editar_troca_fotos_e_professor_e_apaga_arquivos_antigos(app, client_admin):
    enviar(client_admin, "/admin/cursos/novo", professor_foto=foto("ana.png"), fotos=[foto("a.png"), foto("b.png")])
    c = curso()
    antiga_professor, primeira = c.professor_foto, c.imagens[0]
    r = enviar(client_admin, f"/admin/cursos/{c.id}/editar", turma="aberta",
               remover_fotos=[str(primeira.id)], fotos=[foto("c.png")], professor_foto=foto("nova.png"))
    assert r.status_code == 302
    db.session.expire_all()
    c = curso()
    assert len(c.imagens) == 2 and primeira.id not in [i.id for i in c.imagens]
    assert c.professor_foto != antiga_professor
    assert os.path.basename(antiga_professor) not in arquivos(app)
    assert os.path.basename(primeira.caminho) not in arquivos(app) and len(arquivos(app)) == 3


def test_editar_remove_foto_do_professor(app, client_admin):
    enviar(client_admin, "/admin/cursos/novo", professor_foto=foto("ana.png"))
    c = curso()
    enviar(client_admin, f"/admin/cursos/{c.id}/editar", remover_foto_professor="on")
    db.session.expire_all()
    assert curso().professor_foto == "" and arquivos(app) == []


def test_editar_nao_remove_foto_de_outro_curso(client_admin):
    enviar(client_admin, "/admin/cursos/novo", fotos=[foto()])
    outro = Course(titulo="Outro", slug="outro")
    db.session.add(outro)
    db.session.commit()
    imagem = curso().imagens[0]
    enviar(client_admin, f"/admin/cursos/{outro.id}/editar", titulo="Outro", remover_fotos=[str(imagem.id)])
    assert db.session.get(CourseImage, imagem.id) is not None


def test_excluir_curso_apaga_as_fotos(app, client_admin):
    enviar(client_admin, "/admin/cursos/novo", professor_foto=foto("ana.png"), fotos=[foto()])
    client_admin.post(f"/admin/cursos/{curso().id}/excluir")
    assert Course.query.count() == 0 and CourseImage.query.count() == 0 and arquivos(app) == []


def test_formulario_do_painel_tem_os_campos_novos(client_admin):
    html = client_admin.get("/admin/cursos/novo").get_data(as_text=True)
    assert 'enctype="multipart/form-data"' in html
    for campo in ('name="turma" value="aberta"', 'name="turma" value="fechada"', 'name="professor_nome"',
                  'name="professor_instagram"', 'name="professor_foto"', 'name="fotos"'):
        assert campo in html


def test_lista_do_painel_mostra_a_turma(client_admin):
    db.session.add(Course(titulo="Torno básico", slug="torno", turma_aberta=False))
    db.session.commit()
    assert "Turma fechada" in client_admin.get("/admin/cursos").get_data(as_text=True)


# ---------- Página de cursos ----------

def cartao(html, titulo):
    return re.search(rf'<article class="curso".*?{titulo}.*?</article>', html, re.S).group(0)


@pytest.mark.parametrize("aberta, selo", [(True, "Turma aberta"), (False, "Turma fechada")])
def test_formulario_e_whatsapp_aparecem_com_turma_aberta_ou_fechada(app, client, aberta, selo):
    db.session.add(Course(titulo="Torno básico", slug="torno", turma_aberta=aberta))
    db.session.commit()
    html = cartao(client.get("/cursos").get_data(as_text=True), "Torno básico")
    assert selo in html
    assert f'href="{app.config["COURSES_FORM_URL"]}"' in html
    assert "wa.me/" in html and "Torno%20b%C3%A1sico" in html


def test_pagina_mostra_fotos_e_quem_ensina(client):
    c = Course(titulo="Torno básico", slug="torno", professor_nome="Ana Souza", professor_instagram="ana.ceramica",
               professor_foto="img/inicio/vertical-julia-480.webp")
    c.imagens.append(CourseImage(caminho="img/inicio/carrossel-aula-800.webp", ordem=0))
    db.session.add(c)
    db.session.commit()
    html = cartao(client.get("/cursos").get_data(as_text=True), "Torno básico")
    assert "carrossel-aula-800.webp" in html and "vertical-julia-480.webp" in html
    assert "Ana Souza" in html
    assert 'href="https://www.instagram.com/ana.ceramica" target="_blank" rel="noopener"' in html


def test_curso_sem_professor_nao_mostra_o_bloco(client):
    db.session.add(Course(titulo="Torno básico", slug="torno"))
    db.session.commit()
    assert "Quem ensina" not in client.get("/cursos").get_data(as_text=True)


# ---------- Demo ----------

def test_demo_tem_turma_fechada_fotos_e_professor(app):
    assert app.test_cli_runner().invoke(args=["seed-demo"]).exit_code == 0
    cursos = Course.query.all()
    assert any(not c.turma_aberta for c in cursos) and any(c.turma_aberta for c in cursos)
    assert all(c.imagens and c.professor_nome for c in cursos)
