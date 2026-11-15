"""Área do cliente: dados, endereço, favoritos e histórico de pedidos (/conta/...).

Isolamento entre clientes (o erro que mais derruba loja online):
- toda consulta filtra pelo dono: filter_by(..., user_id=current_user.id);
- dado de outra pessoa pedido pela URL responde 404, nunca 403 (não revela que existe);
- o endereço nem tem ID na URL: /conta/endereco é sempre o de quem está logado.
"""
from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user

from ..extensions import db
from ..models import Category, Endereco, Favorito, Pedido, Product, User
from ..utils import destino_seguro
from ..validators import UFS, validar_endereco, validar_telefone

bp = Blueprint("cliente", __name__, url_prefix="/conta")

SENHA_MINIMA = 8


@bp.before_request
def exigir_login():
    """Vale para TODAS as rotas deste blueprint, inclusive as futuras."""
    if current_user.is_authenticated:
        return None
    if request.method == "GET":
        return current_app.login_manager.unauthorized()
    # POST sem login (ex.: sessão expirou): volta pra peça, não pro endereço do POST
    destino = url_for("shop.lista")
    if request.endpoint == "cliente.favoritar":
        produto = db.session.get(Product, request.view_args["produto_id"])
        if produto:
            destino = url_for("shop.produto", slug=produto.slug)
    flash("Entre na sua conta para salvar favoritos.", "erro")
    return redirect(url_for("account.login", next=destino))


@bp.app_template_global()
def favoritado(produto):
    """Usado no coração do cartão e da peça. Uma consulta por página.

    O cache fica no objeto da requisição (novo a cada requisição), e não em `g`,
    que nos testes dura o teste inteiro e devolveria uma lista velha.
    """
    if not current_user.is_authenticated:
        return False
    ids = getattr(request, "_favoritos_ids", None)
    if ids is None:
        ids = {pid for (pid,) in db.session.query(Favorito.produto_id).filter_by(user_id=current_user.id)}
        request._favoritos_ids = ids
    return produto.id in ids


# ---------- Dados pessoais ----------

@bp.route("/dados", methods=["GET", "POST"])
def dados():
    valores = {"nome": current_user.nome, "email": current_user.email,
               "telefone": current_user.telefone or ""}

    if request.method == "POST":
        valores = {k: request.form.get(k, "").strip() for k in ("nome", "email", "telefone")}
        valores["email"] = valores["email"].lower()
        telefone = validar_telefone(valores["telefone"])
        trocou_email = valores["email"] != current_user.email

        erros = []
        if not valores["nome"] or len(valores["nome"]) > 120:
            erros.append("Informe seu nome (até 120 caracteres).")
        if telefone is None:
            erros.append("Telefone com DDD, por exemplo (12) 99139-9090.")
        if trocou_email:
            if "@" not in valores["email"] or len(valores["email"]) > 255:
                erros.append("Informe um e-mail válido.")
            elif not current_user.check_password(request.form.get("senha_atual", "")):
                erros.append("Para trocar o e-mail, confirme sua senha atual.")
            elif User.query.filter_by(email=valores["email"]).first():
                erros.append("Já existe uma conta com esse e-mail.")

        if erros:
            for erro in erros:
                flash(erro, "erro")
        else:
            current_user.nome = valores["nome"]
            current_user.telefone = telefone or None
            current_user.email = valores["email"]
            db.session.commit()
            flash("Dados atualizados.", "ok")
            return redirect(url_for("cliente.dados"))

    return render_template("account/dados.html", valores=valores)


@bp.route("/senha", methods=["POST"])
def senha():
    nova = request.form.get("nova_senha", "")
    erros = []
    if not current_user.check_password(request.form.get("senha_atual", "")):
        erros.append("Senha atual incorreta.")
    if len(nova) < SENHA_MINIMA:
        erros.append(f"A nova senha precisa ter pelo menos {SENHA_MINIMA} caracteres.")
    if nova != request.form.get("confirmacao", ""):
        erros.append("As senhas novas não conferem.")

    if erros:
        for erro in erros:
            flash(erro, "erro")
    else:
        current_user.set_password(nova)
        db.session.commit()
        flash("Senha alterada.", "ok")
    return redirect(url_for("cliente.dados"))


# ---------- Endereço (um por cliente) ----------

@bp.route("/endereco", methods=["GET", "POST"])
def endereco():
    atual = Endereco.query.filter_by(user_id=current_user.id).first()
    valores = {campo: getattr(atual, campo) if atual else ""
               for campo in ("cep", "logradouro", "numero", "complemento", "bairro", "cidade", "uf")}
    if atual:
        valores["cep"] = atual.cep_formatado

    if request.method == "POST":
        dados, erros = validar_endereco(request.form)
        valores = {**dados, "cep": request.form.get("cep", "").strip()}
        if erros:
            for erro in erros:
                flash(erro, "erro")
        else:
            if atual is None:
                atual = Endereco(user_id=current_user.id)
                db.session.add(atual)
            for campo, valor in dados.items():
                setattr(atual, campo, valor)
            db.session.commit()
            flash("Endereço salvo.", "ok")
            return redirect(url_for("cliente.endereco"))

    return render_template("account/endereco.html", valores=valores, endereco=atual, ufs=UFS)


# ---------- Favoritos ----------

@bp.route("/favoritos")
def favoritos():
    lista = (
        Favorito.query.filter_by(user_id=current_user.id)
        .order_by(Favorito.criado_em.desc())
        .all()
    )
    return render_template("account/favoritos.html", favoritos=lista)


@bp.route("/favoritos/<int:produto_id>", methods=["POST"])
def favoritar(produto_id):
    """acao=adicionar|remover. Explícito (e não "alternar"): dois toques seguidos não desfazem."""
    voltar = request.form.get("voltar", "")
    # Sempre filtrado pela pessoa logada: nunca mexe no favorito de outra conta
    existente = Favorito.query.filter_by(user_id=current_user.id, produto_id=produto_id).first()

    if request.form.get("acao") == "remover":
        # Remover vale mesmo se a peça foi desativada depois (senão o favorito ficaria preso)
        produto = db.session.get(Product, produto_id) or abort(404)
        if existente:
            db.session.delete(existente)
            db.session.commit()
        flash(f"“{produto.nome}” saiu dos favoritos.", "ok")
    else:
        # Só favorita o que está à venda
        produto = (
            Product.query.join(Category)
            .filter(Product.id == produto_id, Product.ativo.is_(True), Category.ativa.is_(True))
            .first_or_404()
        )
        if not existente:
            db.session.add(Favorito(user_id=current_user.id, produto_id=produto.id))
            db.session.commit()
        flash(f"“{produto.nome}” está nos seus favoritos.", "ok")

    if destino_seguro(voltar):
        return redirect(voltar)
    return redirect(url_for("shop.produto", slug=produto.slug))


# ---------- Pedidos ----------

@bp.route("/pedidos")
def pedidos():
    lista = (
        Pedido.query.filter_by(user_id=current_user.id)
        .order_by(Pedido.criado_em.desc(), Pedido.id.desc())
        .all()
    )
    return render_template("account/pedidos.html", pedidos=lista)


@bp.route("/pedidos/<int:pedido_id>")
def pedido(pedido_id):
    # Filtro pelo dono: pedido de outra pessoa = 404 (igual a pedido inexistente)
    item = Pedido.query.filter_by(id=pedido_id, user_id=current_user.id).first_or_404()
    return render_template("account/pedido.html", pedido=item)
