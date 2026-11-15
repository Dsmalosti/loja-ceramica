"""Números do painel inicial da Julia ("hoje" e "este mês" no horário de Brasília).

Faturamento = pedidos pagos, enviados ou entregues, contados pela data em que FORAM PAGOS.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func

from ..extensions import db
from ..models import Pedido
from ..utils import FUSO_BRASILIA

FATURADOS = ("pago", "enviado", "entregue")


def _limites(agora):
    """Início de hoje, de amanhã, do mês e do próximo mês (em UTC), contados em Brasília."""
    local = agora.astimezone(FUSO_BRASILIA)
    dia = local.replace(hour=0, minute=0, second=0, microsecond=0)
    mes = dia.replace(day=1)
    proximo_mes = mes.replace(year=mes.year + (mes.month == 12), month=mes.month % 12 + 1)
    return tuple(m.astimezone(timezone.utc) for m in (dia, dia + timedelta(days=1), mes, proximo_mes))


def _soma(inicio, fim):
    qtd, total = (
        db.session.query(func.count(Pedido.id), func.coalesce(func.sum(Pedido.total_centavos), 0))
        .filter(Pedido.status.in_(FATURADOS), Pedido.pago_em >= inicio, Pedido.pago_em < fim)
        .one()
    )
    return int(qtd), int(total)


def numeros(agora=None):
    agora = agora or datetime.now(timezone.utc)
    inicio_dia, fim_dia, inicio_mes, fim_mes = _limites(agora)
    hoje_qtd, hoje_total = _soma(inicio_dia, fim_dia)
    mes_qtd, mes_total = _soma(inicio_mes, fim_mes)
    return {
        "hoje_qtd": hoje_qtd,
        "hoje_total": hoje_total,
        "mes_qtd": mes_qtd,
        "mes_total": mes_total,
        "ticket_medio": mes_total // mes_qtd if mes_qtd else 0,
        "aguardando": Pedido.query.filter_by(status="aguardando_pagamento").count(),
        "a_preparar": Pedido.query.filter_by(status="pago").count(),
        "a_enviar": Pedido.query.filter_by(status="pago", entrega_tipo="entrega").count(),
        "estoque_insuficiente": Pedido.query.filter(
            Pedido.estoque_insuficiente.is_(True), Pedido.status.in_(("pago", "enviado"))
        ).count(),
        "ultimos": Pedido.query.order_by(Pedido.criado_em.desc(), Pedido.id.desc()).limit(5).all(),
    }
