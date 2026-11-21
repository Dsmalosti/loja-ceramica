"""Checkout: resumo → pedido → Mercado Pago → volta.

O cliente nunca digita cartão aqui: o pagamento acontece na página do Mercado Pago.
Preço e total são calculados no servidor. Por enquanto todo pedido é retirado no ateliê.
"""
import secrets

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user

from ..extensions import db
from ..models import ItemPedido, Pedido
from ..services import carrinho, mercadopago
from ..services.pedidos import registrar
from ..validators import validar_telefone

bp = Blueprint("checkout", __name__, url_prefix="/checkout")

CHAVE_TOKEN = "checkout_token"
CHAVE_VALOR_VISTO = "checkout_subtotal_visto"


@bp.before_request
def exigir_login():
    """Vale para TODAS as rotas deste blueprint, inclusive as futuras."""
    if current_user.is_authenticated:
        return None
    if request.method == "GET":
        return current_app.login_manager.unauthorized()
    flash("Entre na sua conta para finalizar a compra.", "erro")
    return redirect(url_for("account.login", next=url_for("checkout.resumo")))


@bp.route("/")
def resumo():
    linhas, subtotal, avisos = carrinho.detalhar(session)
    for aviso in avisos:
        flash(aviso, "erro")
    if not linhas:
        flash("Seu carrinho está vazio.", "erro")
        return redirect(url_for("cart.ver"))

    # Token de uso único: um segundo clique em "Pagar" não cria um segundo pedido
    session[CHAVE_TOKEN] = secrets.token_urlsafe(16)
    # Guarda o valor que a pessoa VIU: se uma promoção começar/acabar até ela confirmar, avisamos
    session[CHAVE_VALOR_VISTO] = subtotal
    return render_template(
        "checkout/resumo.html",
        linhas=linhas,
        subtotal_centavos=subtotal,
        token=session[CHAVE_TOKEN],
        pagamento_disponivel=mercadopago.configurado(),
        telefone=current_user.telefone or "",  # [back/seguranca-auditoria] campo de WhatsApp já preenchido
    )


@bp.route("/confirmar", methods=["POST"])
def confirmar():
    token = session.pop(CHAVE_TOKEN, None)
    if not token or not secrets.compare_digest(token, request.form.get("token", "")):
        flash("Esse pedido já foi enviado. Confira em Meus pedidos.", "erro")
        return redirect(url_for("cliente.pedidos"))

    if not mercadopago.configurado():
        flash("Pagamento indisponível no momento. Fale com o ateliê pelo WhatsApp.", "erro")
        return redirect(url_for("checkout.resumo"))

    # [back/compra-por-loja] Antes havia "entrega" com frete fixo e cópia do endereço. Ela volta com a
    # transportadora (#30); os campos do pedido continuam no banco para esse dia.
    if request.form.get("entrega", "retirada") != "retirada":
        flash("Por enquanto os pedidos são retirados no ateliê.", "erro")
        return redirect(url_for("checkout.resumo"))

    # [back/seguranca-auditoria] Antes o telefone era opcional e o checkout nem perguntava, mas o resumo
    # promete "avisamos pelo WhatsApp quando o pedido estiver pronto". Sem telefone a Julia não tinha como avisar.
    telefone = validar_telefone(request.form.get("telefone", current_user.telefone or ""))
    if not telefone:
        flash("Informe um WhatsApp com DDD, por exemplo (12) 99139-9090, para avisarmos quando o pedido "
              "estiver separado.", "erro")
        return redirect(url_for("checkout.resumo"))
    if telefone != current_user.telefone:
        current_user.telefone = telefone  # vale também para as próximas compras (Meus dados)

    # Revalida tudo pelo banco: se estoque ou disponibilidade mudou, a pessoa revisa antes
    linhas, subtotal, avisos = carrinho.detalhar(session)
    if avisos or not linhas:
        for aviso in avisos:
            flash(aviso, "erro")
        return redirect(url_for("checkout.resumo") if linhas else url_for("cart.ver"))
    if subtotal != session.pop(CHAVE_VALOR_VISTO, None):
        flash("O preço mudou desde que você abriu o resumo (uma promoção começou ou terminou). "
              "Confira o novo total antes de pagar.", "erro")
        return redirect(url_for("checkout.resumo"))

    pedido = Pedido(user_id=current_user.id, status="aguardando_pagamento", entrega_tipo="retirada",
                    subtotal_centavos=subtotal, frete_centavos=0, total_centavos=subtotal)
    for linha in linhas:
        # Cópia do nome e do preço de hoje: o pedido é um documento
        com_desconto = linha.preco.tem_desconto
        pedido.itens.append(ItemPedido(produto_id=linha.produto.id, nome_produto=linha.produto.nome,
                                       preco_unitario_centavos=linha.preco_unitario_centavos,
                                       preco_original_centavos=linha.preco.original if com_desconto else None,
                                       quantidade=linha.quantidade))
    registrar(pedido, None, "aguardando_pagamento", "cliente", current_user)
    db.session.add(pedido)
    db.session.commit()  # o pedido existe mesmo se o Mercado Pago estiver fora do ar
    carrinho.limpar(session)

    return _ir_para_pagamento(pedido)


@bp.route("/pagar/<int:pedido_id>", methods=["POST"])
def pagar(pedido_id):
    """Botão "Pagar agora" de um pedido que ficou aguardando."""
    pedido = Pedido.query.filter_by(id=pedido_id, user_id=current_user.id).first_or_404()
    if pedido.status != "aguardando_pagamento":
        flash("Esse pedido não está aguardando pagamento.", "erro")
        return redirect(url_for("cliente.pedido", pedido_id=pedido.id))
    return _ir_para_pagamento(pedido, nova_preferencia=True)


def _ir_para_pagamento(pedido, nova_preferencia=False):
    try:
        if nova_preferencia or not pedido.mp_init_point:
            # A preferência expira em 2h: ao pagar depois, abre uma nova
            mercadopago.criar_preferencia(pedido)
            db.session.commit()
    except mercadopago.ErroMercadoPago:
        db.session.rollback()
        current_app.logger.exception("Falha ao criar a preferência do pedido %s", pedido.id)
        flash("Seu pedido foi registrado, mas não conseguimos abrir o pagamento agora. "
              "Tente de novo pelo botão “Pagar agora”.", "erro")
        return redirect(url_for("cliente.pedido", pedido_id=pedido.id))
    return redirect(pedido.mp_init_point, code=303)


@bp.route("/retorno/<int:pedido_id>")
def retorno(pedido_id):
    """Volta do Mercado Pago. Não confia no ?status= da URL: confirma com a API."""
    pedido = Pedido.query.filter_by(id=pedido_id, user_id=current_user.id).first_or_404()
    payment_id = request.args.get("payment_id") or request.args.get("collection_id") or ""
    if payment_id.isdigit() and pedido.status == "aguardando_pagamento":
        try:
            mercadopago.processar_pagamento(payment_id)  # mesma função do webhook (idempotente)
        except mercadopago.ErroMercadoPago:
            current_app.logger.warning("Não deu para confirmar o pagamento %s agora", payment_id)
        db.session.refresh(pedido)
    return render_template("checkout/retorno.html", pedido=pedido)
