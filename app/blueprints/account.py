from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from ..extensions import db
from ..models import Endereco, Favorito, Pedido, User
from ..services import carrinho, mensagens
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
    # Quem veio de uma peça (via login) volta pra ela depois de criar a conta
    proximo = request.values.get("next", "")

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
            if destino_seguro(proximo):
                return redirect(proximo)
            return redirect(url_for("account.conta"))

    return render_template("account/cadastro.html", dados=dados, proximo=proximo)


@bp.route("/esqueci-senha", methods=["GET", "POST"])
def esqueci_senha():
    if current_user.is_authenticated:
        return redirect(url_for("account.conta"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        usuario = User.query.filter_by(email=email).first() if email else None
        if usuario and usuario.ativo:
            mensagens.enviar_recuperacao_senha(usuario)
        # Mesma resposta exista a conta ou não (não revela quem é cliente)
        flash("Se esse e-mail tiver conta, enviamos um link para criar uma nova senha. "
              "Confira também o spam.", "ok")
        return redirect(url_for("account.login"))

    return render_template("account/esqueci_senha.html")


@bp.route("/redefinir-senha/<token>", methods=["GET", "POST"])
def redefinir_senha(token):
    usuario = mensagens.usuario_do_token(token)
    if usuario is None:
        flash("Esse link expirou ou já foi usado. Peça um novo.", "erro")
        return redirect(url_for("account.esqueci_senha"))

    if request.method == "POST":
        senha = request.form.get("senha", "")
        if len(senha) < SENHA_MINIMA:
            flash(f"A senha precisa ter pelo menos {SENHA_MINIMA} caracteres.", "erro")
        elif senha != request.form.get("confirmacao", ""):
            flash("As senhas não conferem.", "erro")
        else:
            usuario.set_password(senha)
            db.session.commit()
            flash("Senha alterada. Entre com a nova senha.", "ok")
            return redirect(url_for("account.login"))

    return render_template("account/redefinir_senha.html")


@bp.route("/sair", methods=["POST"])
def logout():
    # O carrinho mora na sessão do navegador: sem isto, quem entrar depois
    # no mesmo computador herdaria o carrinho da pessoa anterior.
    carrinho.limpar(session)
    logout_user()
    flash("Você saiu da conta.", "ok")
    return redirect(url_for("public.home"))


@bp.route("/conta")
@login_required
def conta():
    # Tudo filtrado pela pessoa logada (isolamento entre clientes)
    ultimo_pedido = (
        Pedido.query.filter_by(user_id=current_user.id)
        .order_by(Pedido.criado_em.desc(), Pedido.id.desc())
        .first()
    )
    return render_template(
        "account/conta.html",
        ultimo_pedido=ultimo_pedido,
        endereco=Endereco.query.filter_by(user_id=current_user.id).first(),
        total_favoritos=Favorito.query.filter_by(user_id=current_user.id).count(),
    )
