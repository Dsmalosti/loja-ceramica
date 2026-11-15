from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user

from ..extensions import db
from ..models import Product
from ..services import carrinho
from ..validators import parse_inteiro

bp = Blueprint("cart", __name__, url_prefix="/carrinho")


@bp.before_request
def exigir_login():
    """Carrinho só com login. Vale para TODAS as rotas deste blueprint, inclusive as futuras."""
    if current_user.is_authenticated:
        return None
    if request.method == "GET":
        # O Flask-Login monta o ?next= com o endereço atual (ex.: /carrinho/)
        return current_app.login_manager.unauthorized()
    # POST: depois do login o navegador faria GET no endereço do POST (erro 405).
    # Então a volta é pra peça (adicionar) ou pro carrinho (demais ações).
    destino = url_for("cart.ver")
    if request.endpoint == "cart.adicionar":
        produto = db.session.get(Product, request.view_args["produto_id"])
        destino = url_for("shop.produto", slug=produto.slug) if produto else url_for("shop.lista")
    flash("Entre na sua conta para comprar.", "erro")
    return redirect(url_for("account.login", next=destino))


@bp.app_context_processor
def injetar_carrinho():
    # Número mostrado no menu do site (lê só a sessão, não consulta o banco)
    return {"carrinho_qtd": carrinho.quantidade_total(session)}


def _quantidade(padrao=1):
    """Lê o campo 'quantidade' do formulário. Devolve None se for inválido."""
    texto = request.form.get("quantidade")
    if texto is None or texto.strip() == "":
        return padrao
    return parse_inteiro(texto, maximo=carrinho.MAX_POR_ITEM)


def _avisar(situacao, produto, final):
    if situacao == "indisponivel":
        flash(f"“{produto.nome}” não está disponível no momento.", "erro")
    elif situacao == "limitado":
        flash(f"Só temos {final} de “{produto.nome}” em estoque; o carrinho foi ajustado.", "erro")


@bp.route("/")
def ver():
    linhas, total, avisos = carrinho.detalhar(session)
    for aviso in avisos:
        flash(aviso, "erro")
    return render_template("cart/carrinho.html", linhas=linhas, total_centavos=total)


@bp.route("/adicionar/<int:produto_id>", methods=["POST"])
def adicionar(produto_id):
    produto = db.get_or_404(Product, produto_id)
    quantidade = _quantidade()
    if not quantidade:  # None (inválido) ou 0
        flash("Escolha uma quantidade de 1 em diante.", "erro")
        return redirect(url_for("shop.produto", slug=produto.slug))

    situacao, final = carrinho.adicionar(session, produto, quantidade)
    _avisar(situacao, produto, final)
    if situacao == "indisponivel":
        return redirect(url_for("shop.lista"))
    if situacao == "ok":
        flash(f"“{produto.nome}” foi para o carrinho.", "ok")
    return redirect(url_for("cart.ver"))


@bp.route("/atualizar/<int:produto_id>", methods=["POST"])
def atualizar(produto_id):
    produto = db.get_or_404(Product, produto_id)
    quantidade = _quantidade(padrao=None)
    if quantidade is None:
        flash("Quantidade inválida.", "erro")
    else:
        situacao, final = carrinho.definir(session, produto, quantidade)
        _avisar(situacao, produto, final)
    return redirect(url_for("cart.ver"))


@bp.route("/remover/<int:produto_id>", methods=["POST"])
def remover(produto_id):
    carrinho.remover(session, produto_id)
    flash("Item removido do carrinho.", "ok")
    return redirect(url_for("cart.ver"))


@bp.route("/limpar", methods=["POST"])
def limpar():
    carrinho.limpar(session)
    flash("Carrinho esvaziado.", "ok")
    return redirect(url_for("cart.ver"))
