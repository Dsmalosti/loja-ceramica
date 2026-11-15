"""Ciclo de vida do pedido: quais mudanças de status são permitidas e o que cada uma faz.

  aguardando_pagamento -> cancelado            (pago só pelo Mercado Pago, nunca à mão)
  pago -> enviado (entrega) | entregue (retirada) | cancelado (peças voltam ao estoque)
  enviado -> entregue ; entregue e cancelado são finais

Toda mudança entra no histórico (HistoricoStatus) com a origem e, se for gente, quem fez.
"""
from sqlalchemy import update

from ..extensions import db
from ..models import HistoricoStatus, Product

TRANSICOES = {
    "aguardando_pagamento": ("cancelado",),
    "pago": ("enviado", "entregue", "cancelado"),
    "enviado": ("entregue",),
    "entregue": (),
    "cancelado": (),
}

ROTULOS_ACAO = {
    "enviado": "Marcar como enviado",
    "entregue": "Marcar como entregue",
    "cancelado": "Cancelar pedido",
}


class TransicaoInvalida(Exception):
    pass


def proximos(pedido):
    """Status para onde ESTE pedido pode ir agora (depende de entrega ou retirada)."""
    opcoes = list(TRANSICOES.get(pedido.status, ()))
    if pedido.status == "pago":
        # Entrega passa por "enviado"; retirada vai direto pra "entregue" (retirado no ateliê)
        opcoes.remove("entregue" if pedido.entrega_tipo == "entrega" else "enviado")
    return opcoes


def registrar(pedido, de, para, origem, por=None):
    pedido.historico.append(HistoricoStatus(de=de, para=para, origem=origem,
                                            por_user_id=por.id if por else None))


def mudar_status(pedido, novo, por):
    """Mudança feita no painel. Devolve lista de avisos. Lança TransicaoInvalida.

    Não faz commit: quem chama decide (a rota faz commit; os testes conferem).
    """
    if novo not in proximos(pedido):
        raise TransicaoInvalida(f"Não dá para passar de “{pedido.status_texto}” para “{novo}”.")

    avisos = []
    if novo == "cancelado" and pedido.status == "pago":
        if pedido.estoque_insuficiente:
            # A baixa pode não ter acontecido pra todas as peças: devolver às cegas inventaria estoque
            avisos.append("Pedido tinha estoque insuficiente: confira o estoque das peças à mão.")
        else:
            for item in pedido.itens:
                db.session.execute(
                    update(Product).where(Product.id == item.produto_id)
                    .values(estoque=Product.estoque + item.quantidade)
                )
            avisos.append("As peças voltaram para o estoque. Lembre de devolver o dinheiro no Mercado Pago.")

    registrar(pedido, pedido.status, novo, "painel", por)
    pedido.status = novo
    return avisos
