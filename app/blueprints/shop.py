from flask import Blueprint, abort, render_template, request
from flask_login import login_required

from ..lojas import LOJA_PECAS, LOJAS
from ..models import Category, Product
from ..services.catalogo import BUSCA_MAXIMA, filtrar_por_busca, produtos_da_loja

bp = Blueprint("shop", __name__, url_prefix="/loja")


@bp.route("/")
def lista():
    # [back/duas-lojas] Antes havia uma loja só, com todas as categorias e sem busca.
    # A categoria decide a loja: links antigos (/loja/?categoria=x) continuam certos.
    categoria_atual = None
    slug = request.args.get("categoria")
    if slug:
        categoria_atual = Category.query.filter_by(slug=slug, ativa=True).first_or_404()
        loja = categoria_atual.loja
    else:
        loja = request.args.get("loja", LOJA_PECAS)
        if loja not in LOJAS:
            abort(404)

    busca = request.args.get("q", "").strip()[:BUSCA_MAXIMA]
    produtos = produtos_da_loja(loja, categoria_atual)
    if busca:
        produtos = filtrar_por_busca(produtos, busca)

    categorias = Category.query.filter_by(ativa=True, loja=loja).order_by(Category.nome).all()
    return render_template(
        "shop/lista.html",
        produtos=produtos,
        categorias=categorias,
        categoria_atual=categoria_atual,
        loja_atual=loja,
        busca=busca,
        busca_maxima=BUSCA_MAXIMA,
    )


@bp.route("/<slug>")
@login_required  # Regra da Julia: catálogo aberto, detalhe e compra só com login
def produto(slug):
    item = (
        Product.query.join(Category)
        .filter(Product.slug == slug, Product.ativo.is_(True), Category.ativa.is_(True))
        .first_or_404()
    )
    # [back/duas-lojas] loja_atual marca a loja certa no menu
    return render_template("shop/produto.html", produto=item, loja_atual=item.categoria.loja)
