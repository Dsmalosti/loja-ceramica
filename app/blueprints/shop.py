from flask import Blueprint, render_template, request

from ..models import Category, Product

bp = Blueprint("shop", __name__, url_prefix="/loja")


@bp.route("/")
def lista():
    categorias = Category.query.filter_by(ativa=True).order_by(Category.nome).all()
    consulta = Product.query.join(Category).filter(
        Product.ativo.is_(True), Category.ativa.is_(True)
    )

    categoria_atual = None
    slug = request.args.get("categoria")
    if slug:
        categoria_atual = Category.query.filter_by(slug=slug, ativa=True).first_or_404()
        consulta = consulta.filter(Product.categoria_id == categoria_atual.id)

    produtos = consulta.order_by(Product.nome).all()
    return render_template(
        "shop/lista.html",
        produtos=produtos,
        categorias=categorias,
        categoria_atual=categoria_atual,
    )


@bp.route("/<slug>")
def produto(slug):
    item = (
        Product.query.join(Category)
        .filter(Product.slug == slug, Product.ativo.is_(True), Category.ativa.is_(True))
        .first_or_404()
    )
    return render_template("shop/produto.html", produto=item)
