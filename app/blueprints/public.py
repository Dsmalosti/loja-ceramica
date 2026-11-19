from flask import Blueprint, redirect, render_template, url_for

from ..lojas import LOJA_PECAS, LOJA_PRODUTOS
from ..models import Category, Course, Service
from ..services.catalogo import novidades_da_loja

bp = Blueprint("public", __name__)


@bp.route("/")
def home():
    # [back/duas-lojas] Antes: 4 produtos mais novos e todas as categorias, sem separar por loja
    categorias = Category.query.filter_by(ativa=True, loja=LOJA_PECAS).order_by(Category.nome).all()
    return render_template(
        "public/home.html",
        produtos_destaque=novidades_da_loja(LOJA_PECAS),
        produtos_ceramistas=novidades_da_loja(LOJA_PRODUTOS),
        categorias=categorias,
    )


@bp.route("/cursos")
def cursos():
    lista = Course.query.filter_by(ativo=True).order_by(Course.titulo).all()
    return render_template("public/cursos.html", cursos=lista)


@bp.route("/servicos")
def servicos():
    lista = Service.query.filter_by(ativo=True).order_by(Service.titulo).all()
    return render_template("public/servicos.html", servicos=lista)


@bp.route("/pecas-personalizadas")
def pecas_personalizadas():
    # [back/duas-lojas] Antes: página própria. O conteúdo foi para Serviços; o link antigo continua valendo.
    return redirect(url_for("public.servicos", _anchor="personalizadas"), code=301)


@bp.route("/sobre")
def sobre():
    return render_template("public/sobre.html")


@bp.route("/contato")
def contato():
    # [back/duas-lojas] Antes: página própria. O contato agora é o fim de Sobre nós.
    return redirect(url_for("public.sobre", _anchor="contato"), code=301)
