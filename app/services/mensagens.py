"""Monta e envia os e-mails da loja (recuperação de senha e pedidos)."""
import logging

from flask import current_app, render_template, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from ..extensions import db
from ..models import User
from ..utils import brl
from . import email

log = logging.getLogger(__name__)

SALT_SENHA = "redefinir-senha"
VALIDADE_SENHA = 3600  # 1 hora


def _link(endpoint, **valores):
    """Link completo (e-mail não tem 'site atual'): usa SITE_URL quando existe."""
    caminho = url_for(endpoint, **valores)
    base = current_app.config.get("SITE_URL")
    return base + caminho if base else url_for(endpoint, _external=True, **valores)


def _selo(usuario):
    # Muda quando a senha muda: o link já usado (ou antigo) deixa de valer
    import hashlib
    return hashlib.sha256((usuario.password_hash or "").encode()).hexdigest()[:16]


def _serializador():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=SALT_SENHA)


def gerar_token_senha(usuario):
    return _serializador().dumps({"id": usuario.id, "s": _selo(usuario)})


def usuario_do_token(token):
    """Devolve o usuário dono do token, ou None (inválido, expirado ou já usado)."""
    try:
        dados = _serializador().loads(token, max_age=VALIDADE_SENHA)
    except (BadSignature, SignatureExpired):
        return None
    usuario = db.session.get(User, dados.get("id")) if isinstance(dados, dict) else None
    if usuario is None or not usuario.ativo or dados.get("s") != _selo(usuario):
        return None
    return usuario


def enviar_recuperacao_senha(usuario):
    contexto = {"nome": usuario.nome, "site_name": current_app.config["SITE_NAME"],
                "link": _link("account.redefinir_senha", token=gerar_token_senha(usuario))}
    return email.enviar(
        usuario.email,
        f"Redefinir sua senha · {contexto['site_name']}",
        render_template("email/recuperar_senha.txt", **contexto),
        render_template("email/recuperar_senha.html", **contexto),
        nome_para=usuario.nome,
    )


def _contexto_pedido(pedido):
    return {
        "pedido": pedido, "brl": brl, "site_name": current_app.config["SITE_NAME"],
        "retirada": pedido.entrega_tipo == "retirada",
        "link_cliente": _link("cliente.pedido", pedido_id=pedido.id),
        "link_admin": _link("admin.pedido_detalhe", pedido_id=pedido.id),
    }


def enviar_pedido_pago(pedido):
    """Confirmação para a cliente e aviso para a Julia. Nunca lança erro."""
    try:
        ctx = _contexto_pedido(pedido)
        if pedido.usuario and pedido.usuario.email:
            email.enviar(
                pedido.usuario.email,
                f"Pagamento confirmado · pedido #{pedido.id}",
                render_template("email/pedido_cliente.txt", **ctx),
                render_template("email/pedido_cliente.html", **ctx),
                nome_para=pedido.usuario.nome,
            )
        aviso = current_app.config.get("EMAIL_AVISO_PEDIDOS")
        if aviso:
            email.enviar(
                aviso,
                f"Novo pedido pago #{pedido.id} · {brl(pedido.total_centavos)}",
                render_template("email/pedido_julia.txt", **ctx),
                render_template("email/pedido_julia.html", **ctx),
                # [back/emails-brevo] Antes a resposta voltava para o próprio ateliê. Agora a Julia
                # clica em Responder e fala direto com quem comprou.
                responder_para=pedido.usuario.email if pedido.usuario else None,
            )
    except Exception:
        log.exception("Falha ao montar os e-mails do pedido %s", getattr(pedido, "id", "?"))
