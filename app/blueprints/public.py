from flask import Blueprint, render_template

from ..models import Category, Course, Product, Service

bp = Blueprint("public", __name__)


@bp.route("/")
def home():
    produtos_destaque = (
        Product.query.join(Category)
        .filter(Product.ativo.is_(True), Category.ativa.is_(True))
        .order_by(Product.criado_em.desc())
        .limit(4)
        .all()
    )
    categorias = Category.query.filter_by(ativa=True).order_by(Category.nome).all()
    return render_template(
        "public/home.html", produtos_destaque=produtos_destaque, categorias=categorias
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
    return render_template("public/pecas_personalizadas.html")


@bp.route("/sobre")
def sobre():
    return render_template("public/sobre.html")


@bp.route("/contato")
def contato():
    return render_template("public/contato.html")
