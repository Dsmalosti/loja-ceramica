from flask import flash, redirect, render_template, request, url_for
from sqlalchemy import func

from ..extensions import db
from ..models import Category
from ..services.catalogo import slug_unico
from ..validators import validar_categoria
from .admin import bp


def _nome_ja_usado(nome, ignorar_id=None):
    consulta = Category.query.filter(func.lower(Category.nome) == nome.lower())
    if ignorar_id is not None:
        consulta = consulta.filter(Category.id != ignorar_id)
    return consulta.first() is not None


@bp.route("/categorias")
def categorias_lista():
    categorias = Category.query.order_by(Category.nome).all()
    return render_template("admin/categorias_lista.html", categorias=categorias)


@bp.route("/categorias/nova", methods=["GET", "POST"])
def categoria_nova():
    valores = {"nome": "", "ativa": True}

    if request.method == "POST":
        dados, erros = validar_categoria(request.form)
        valores = dados
        if not erros and _nome_ja_usado(dados["nome"]):
            erros.append("Já existe uma categoria com esse nome.")

        if not erros:
            db.session.add(
                Category(nome=dados["nome"], slug=slug_unico(Category, dados["nome"]), ativa=dados["ativa"])
            )
            db.session.commit()
            flash("Categoria criada.", "ok")
            return redirect(url_for("admin.categorias_lista"))
        for erro in erros:
            flash(erro, "erro")

    return render_template("admin/categoria_form.html", categoria=None, valores=valores)


@bp.route("/categorias/<int:categoria_id>/editar", methods=["GET", "POST"])
def categoria_editar(categoria_id):
    categoria = db.get_or_404(Category, categoria_id)
    valores = {"nome": categoria.nome, "ativa": categoria.ativa}

    if request.method == "POST":
        dados, erros = validar_categoria(request.form)
        valores = dados
        if not erros and _nome_ja_usado(dados["nome"], ignorar_id=categoria.id):
            erros.append("Já existe uma categoria com esse nome.")

        if not erros:
            # O slug não muda ao renomear, para não quebrar links já compartilhados
            categoria.nome = dados["nome"]
            categoria.ativa = dados["ativa"]
            db.session.commit()
            flash("Categoria salva.", "ok")
            return redirect(url_for("admin.categorias_lista"))
        for erro in erros:
            flash(erro, "erro")

    return render_template("admin/categoria_form.html", categoria=categoria, valores=valores)


@bp.route("/categorias/<int:categoria_id>/alternar", methods=["POST"])
def categoria_alternar(categoria_id):
    categoria = db.get_or_404(Category, categoria_id)
    categoria.ativa = not categoria.ativa
    db.session.commit()
    if categoria.ativa:
        flash(f"Categoria “{categoria.nome}” ativada.", "ok")
    else:
        flash(f"Categoria “{categoria.nome}” desativada. Os produtos dela deixam de aparecer na loja.", "ok")
    return redirect(url_for("admin.categorias_lista"))


@bp.route("/categorias/<int:categoria_id>/excluir", methods=["POST"])
def categoria_excluir(categoria_id):
    categoria = db.get_or_404(Category, categoria_id)
    if categoria.produtos:
        flash(
            f"A categoria “{categoria.nome}” tem produtos. Mova ou exclua os produtos antes, "
            "ou apenas desative a categoria.",
            "erro",
        )
        return redirect(url_for("admin.categorias_lista"))

    db.session.delete(categoria)
    db.session.commit()
    flash("Categoria excluída.", "ok")
    return redirect(url_for("admin.categorias_lista"))
