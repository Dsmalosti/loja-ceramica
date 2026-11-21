from flask import Blueprint, current_app, redirect, render_template, request, url_for

from ..lojas import LOJA_PECAS, LOJA_PRODUTOS
from ..models import Category, Course, Product, Service
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
    # [back/painel-julia] Ordem escolhida pela Julia. Antes: alfabética.
    lista = Course.query.filter_by(ativo=True).order_by(Course.ordem, Course.titulo).all()
    return render_template("public/cursos.html", cursos=lista)


@bp.route("/servicos")
def servicos():
    # [back/painel-julia] Ordem escolhida pela Julia. Antes: alfabética.
    lista = Service.query.filter_by(ativo=True).order_by(Service.ordem, Service.titulo).all()
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


# [back/seguranca-auditoria] Novas: a LGPD pede política de privacidade onde há coleta de dados
# (cadastro, checkout). Antes /privacidade e /termos davam 404.
@bp.route("/privacidade")
def privacidade():
    return render_template("public/privacidade.html")


@bp.route("/termos")
def termos():
    return render_template("public/termos.html")


def _base_do_site():
    """Endereço público do site (https://...): o do .env em produção, o da requisição no PC."""
    return current_app.config.get("SITE_URL") or request.url_root.rstrip("/")


# [back/seguranca-auditoria] Novas: robots.txt e sitemap.xml (antes 404). As telas privadas ficam
# fora da busca (também têm noindex no HTML).
@bp.route("/robots.txt")
def robots():
    texto = "\n".join([
        "User-agent: *",
        "Allow: /",
        "Disallow: /admin/",
        "Disallow: /conta/",
        "Disallow: /carrinho/",
        "Disallow: /checkout/",
        f"Sitemap: {_base_do_site()}/sitemap.xml",
        "",
    ])
    return current_app.response_class(texto, mimetype="text/plain")


@bp.route("/sitemap.xml")
def sitemap():
    base = _base_do_site()
    caminhos = [
        url_for("public.home"),
        url_for("shop.lista"),
        url_for("shop.lista", loja=LOJA_PRODUTOS),
        url_for("public.cursos"),
        url_for("public.servicos"),
        url_for("public.sobre"),
        url_for("public.privacidade"),
        url_for("public.termos"),
    ]
    # Só produto que aparece na loja: ativo e de categoria ativa
    produtos = (Product.query.join(Category)
                .filter(Product.ativo.is_(True), Category.ativa.is_(True))
                .order_by(Product.id).all())
    caminhos += [url_for("shop.produto", slug=produto.slug) for produto in produtos]
    xml = render_template("public/sitemap.xml", enderecos=[base + c for c in caminhos])
    return current_app.response_class(xml, mimetype="application/xml")
