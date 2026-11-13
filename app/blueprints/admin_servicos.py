from flask import flash, redirect, render_template, request, url_for

from ..extensions import db
from ..models import Service
from ..validators import validar_servico
from .admin import bp


@bp.route("/servicos")
def servicos_lista():
    servicos = Service.query.order_by(Service.titulo).all()
    return render_template("admin/servicos_lista.html", servicos=servicos)


@bp.route("/servicos/novo", methods=["GET", "POST"])
def servico_novo():
    valores = {"titulo": "", "descricao": "", "ativo": True}

    if request.method == "POST":
        dados, erros = validar_servico(request.form)
        valores = dados

        if not erros:
            db.session.add(
                Service(titulo=dados["titulo"], descricao=dados["descricao"], ativo=dados["ativo"])
            )
            db.session.commit()
            flash("Serviço criado.", "ok")
            return redirect(url_for("admin.servicos_lista"))
        for erro in erros:
            flash(erro, "erro")

    return render_template("admin/servico_form.html", servico=None, valores=valores)


@bp.route("/servicos/<int:servico_id>/editar", methods=["GET", "POST"])
def servico_editar(servico_id):
    servico = db.get_or_404(Service, servico_id)
    valores = {"titulo": servico.titulo, "descricao": servico.descricao, "ativo": servico.ativo}

    if request.method == "POST":
        dados, erros = validar_servico(request.form)
        valores = dados

        if not erros:
            servico.titulo = dados["titulo"]
            servico.descricao = dados["descricao"]
            servico.ativo = dados["ativo"]
            db.session.commit()
            flash("Serviço salvo.", "ok")
            return redirect(url_for("admin.servicos_lista"))
        for erro in erros:
            flash(erro, "erro")

    return render_template("admin/servico_form.html", servico=servico, valores=valores)


@bp.route("/servicos/<int:servico_id>/alternar", methods=["POST"])
def servico_alternar(servico_id):
    servico = db.get_or_404(Service, servico_id)
    servico.ativo = not servico.ativo
    db.session.commit()
    flash(f"Serviço “{servico.titulo}” {'ativado' if servico.ativo else 'desativado'}.", "ok")
    return redirect(url_for("admin.servicos_lista"))


@bp.route("/servicos/<int:servico_id>/excluir", methods=["POST"])
def servico_excluir(servico_id):
    servico = db.get_or_404(Service, servico_id)
    titulo = servico.titulo
    db.session.delete(servico)
    db.session.commit()
    flash(f"Serviço “{titulo}” excluído.", "ok")
    return redirect(url_for("admin.servicos_lista"))
