from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from ..extensions import db
from ..models import User
from ..utils import destino_seguro

bp = Blueprint("account", __name__)

SENHA_MINIMA = 8


@bp.route("/entrar", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("account.conta"))

    # O Flask-Login manda o destino original em ?next=
    proximo = request.values.get("next", "")

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")
        usuario = User.query.filter_by(email=email).first()

        if usuario and usuario.ativo and usuario.check_password(senha):
            login_user(usuario)
            if destino_seguro(proximo):
                return redirect(proximo)
            return redirect(url_for("account.conta"))

        # Mesma mensagem para e-mail inexistente e senha errada
        flash("E-mail ou senha incorretos.", "erro")

    return render_template("account/login.html", proximo=proximo)


@bp.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if current_user.is_authenticated:
        return redirect(url_for("account.conta"))

    dados = {"nome": "", "email": ""}

    if request.method == "POST":
        dados["nome"] = request.form.get("nome", "").strip()
        dados["email"] = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")
        confirmacao = request.form.get("confirmacao", "")

        erros = []
        if not dados["nome"]:
            erros.append("Informe seu nome.")
        if "@" not in dados["email"] or len(dados["email"]) > 255:
            erros.append("Informe um e-mail válido.")
        if len(senha) < SENHA_MINIMA:
            erros.append(f"A senha precisa ter pelo menos {SENHA_MINIMA} caracteres.")
        if senha != confirmacao:
            erros.append("As senhas não conferem.")
        if not erros and User.query.filter_by(email=dados["email"]).first():
            erros.append("Já existe uma conta com esse e-mail.")

        if erros:
            for erro in erros:
                flash(erro, "erro")
        else:
            usuario = User(nome=dados["nome"], email=dados["email"])
            usuario.set_password(senha)
            db.session.add(usuario)
            db.session.commit()
            login_user(usuario)
            flash("Conta criada com sucesso.", "ok")
            return redirect(url_for("account.conta"))

    return render_template("account/cadastro.html", dados=dados)


@bp.route("/sair", methods=["POST"])
def logout():
    logout_user()
    flash("Você saiu da conta.", "ok")
    return redirect(url_for("public.home"))


@bp.route("/conta")
@login_required
def conta():
    # Pedidos e status entram quando o carrinho/checkout estiverem prontos
    return render_template("account/conta.html")
