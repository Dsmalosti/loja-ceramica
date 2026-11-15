from flask import Blueprint, current_app, request

from ..extensions import csrf
from ..services import mercadopago

bp = Blueprint("payments", __name__, url_prefix="/pagamento")


@bp.route("/webhook", methods=["POST"])
@csrf.exempt  # Quem chama é o Mercado Pago, não um formulário nosso: a proteção é a assinatura
def webhook():
    """Aviso do Mercado Pago. Responde rápido; a verdade vem da consulta à API."""
    corpo = request.get_json(silent=True) or {}
    tipo = request.args.get("type") or request.args.get("topic") or corpo.get("type")
    data_id = request.args.get("data.id") or str((corpo.get("data") or {}).get("id") or "")

    if not mercadopago.assinatura_valida(
        request.headers.get("x-signature", ""),
        request.headers.get("x-request-id", ""),
        request.args.get("data.id", ""),
        current_app.config.get("MP_WEBHOOK_SECRET", ""),
    ):
        return "", 401

    if tipo != "payment" or not data_id.isdigit():
        return "", 200  # outros avisos (merchant_order etc.) não interessam

    try:
        mercadopago.processar_pagamento(data_id)
    except mercadopago.ErroMercadoPago:
        current_app.logger.exception("Falha ao consultar o pagamento %s", data_id)
        return "", 500  # o Mercado Pago reenvia depois
    return "", 200
