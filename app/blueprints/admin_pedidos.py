"""Painel: pedidos (lista com filtro e busca, detalhe, mudança de status).

Só acrescenta rotas ao blueprint "admin", que já exige administrador em TODAS as rotas.
A administradora vê pedidos de todos os clientes (é o papel dela); cliente nunca entra aqui (403).
"""
from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import func, or_

from ..extensions import db
from ..models import EventoPagamento, HistoricoStatus, Pedido, User
from ..services.pedidos import ROTULOS_ACAO, TransicaoInvalida, mudar_status, proximos
from ..validators import escapar_like, parse_inteiro
from .admin import bp

POR_PAGINA = 30


@bp.route("/pedidos")
def pedidos_lista():
    status = request.args.get("status", "")
    q = request.args.get("q", "").strip()
    pagina = parse_inteiro(request.args.get("pagina"), maximo=10_000) or 1

    consulta = Pedido.query.join(User, Pedido.user_id == User.id)
    if status in Pedido.STATUS:
        consulta = consulta.filter(Pedido.status == status)
    if q:
        termo = f"%{escapar_like(q)}%"
        filtros = [User.nome.ilike(termo, escape="\\"), User.email.ilike(termo, escape="\\")]
        if q.isdigit():
            filtros.append(Pedido.id == int(q))
        consulta = consulta.filter(or_(*filtros))

    pedidos = consulta.order_by(Pedido.criado_em.desc(), Pedido.id.desc()).paginate(
        page=pagina, per_page=POR_PAGINA, error_out=False
    )
    contagens = dict(db.session.query(Pedido.status, func.count(Pedido.id)).group_by(Pedido.status).all())
    return render_template("admin/pedidos_lista.html", pedidos=pedidos, contagens=contagens,
                           filtros={"status": status, "q": q}, rotulos=Pedido.STATUS)


@bp.route("/pedidos/<int:pedido_id>")
def pedido_detalhe(pedido_id):
    pedido = db.get_or_404(Pedido, pedido_id)
    eventos = (EventoPagamento.query.filter_by(pedido_id=pedido.id)
               .order_by(EventoPagamento.recebido_em, EventoPagamento.id).all())
    return render_template(
        "admin/pedido_detalhe.html",
        pedido=pedido,
        acoes=[(s, ROTULOS_ACAO[s]) for s in proximos(pedido)],
        eventos=eventos,
        tem_estorno=any(e.status in ("refunded", "charged_back") for e in eventos),
    )


@bp.route("/pedidos/<int:pedido_id>/status", methods=["POST"])
def pedido_status(pedido_id):
    pedido = db.get_or_404(Pedido, pedido_id)
    novo = request.form.get("status", "")
    try:
        avisos = mudar_status(pedido, novo, current_user)
    except TransicaoInvalida as erro:
        db.session.rollback()
        flash(str(erro), "erro")
    else:
        db.session.commit()
        flash(f"Pedido nº {pedido.id}: {pedido.status_texto}.", "ok")
        for aviso in avisos:
            flash(aviso, "erro" if "confira" in aviso.lower() else "ok")
    return redirect(url_for("admin.pedido_detalhe", pedido_id=pedido.id))


@bp.app_template_global()
def rotulo_origem(origem):
    return HistoricoStatus.ORIGENS.get(origem, origem)
