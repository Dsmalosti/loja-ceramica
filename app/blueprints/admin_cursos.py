from flask import flash, redirect, render_template, request, url_for

from ..extensions import db
from ..models import Course
from ..services.catalogo import slug_unico
from ..validators import formatar_preco_input, validar_curso
from .admin import bp


def _valores_do_curso(curso):
    return {
        "titulo": curso.titulo,
        "descricao": curso.descricao,
        "duracao": curso.duracao,
        "valor_texto": formatar_preco_input(curso.valor_centavos),
        "ativo": curso.ativo,
    }


@bp.route("/cursos")
def cursos_lista():
    cursos = Course.query.order_by(Course.titulo).all()
    return render_template("admin/cursos_lista.html", cursos=cursos)


@bp.route("/cursos/novo", methods=["GET", "POST"])
def curso_novo():
    valores = {"titulo": "", "descricao": "", "duracao": "", "valor_texto": "", "ativo": True}

    if request.method == "POST":
        dados, erros = validar_curso(request.form)
        valores = dados

        if not erros:
            db.session.add(
                Course(
                    titulo=dados["titulo"],
                    slug=slug_unico(Course, dados["titulo"]),
                    descricao=dados["descricao"],
                    duracao=dados["duracao"],
                    valor_centavos=dados["valor_centavos"],
                    ativo=dados["ativo"],
                )
            )
            db.session.commit()
            flash("Curso criado.", "ok")
            return redirect(url_for("admin.cursos_lista"))
        for erro in erros:
            flash(erro, "erro")

    return render_template("admin/curso_form.html", curso=None, valores=valores)


@bp.route("/cursos/<int:curso_id>/editar", methods=["GET", "POST"])
def curso_editar(curso_id):
    curso = db.get_or_404(Course, curso_id)
    valores = _valores_do_curso(curso)

    if request.method == "POST":
        dados, erros = validar_curso(request.form)
        valores = dados

        if not erros:
            curso.titulo = dados["titulo"]
            curso.descricao = dados["descricao"]
            curso.duracao = dados["duracao"]
            curso.valor_centavos = dados["valor_centavos"]
            curso.ativo = dados["ativo"]
            db.session.commit()
            flash("Curso salvo.", "ok")
            return redirect(url_for("admin.cursos_lista"))
        for erro in erros:
            flash(erro, "erro")

    return render_template("admin/curso_form.html", curso=curso, valores=valores)


@bp.route("/cursos/<int:curso_id>/alternar", methods=["POST"])
def curso_alternar(curso_id):
    curso = db.get_or_404(Course, curso_id)
    curso.ativo = not curso.ativo
    db.session.commit()
    flash(f"Curso “{curso.titulo}” {'ativado' if curso.ativo else 'desativado'}.", "ok")
    return redirect(url_for("admin.cursos_lista"))


@bp.route("/cursos/<int:curso_id>/excluir", methods=["POST"])
def curso_excluir(curso_id):
    curso = db.get_or_404(Course, curso_id)
    titulo = curso.titulo
    db.session.delete(curso)
    db.session.commit()
    flash(f"Curso “{titulo}” excluído.", "ok")
    return redirect(url_for("admin.cursos_lista"))
