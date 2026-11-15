"""Painel: promoções (percentual ou valor fixo, com período, para peças e/ou cursos).

Só acrescenta rotas ao blueprint "admin", que já exige login de administrador
em TODAS as rotas (before_request em admin.py).
"""
from flask import flash, redirect, render_template, request, url_for

from ..extensions import db
from ..models import Course, Product, Promocao
from ..validators import formatar_data_hora_input, formatar_preco_input, validar_promocao
from .admin import bp


def _opcoes():
    produtos = Product.query.order_by(Product.nome).all()
    cursos = Course.query.order_by(Course.titulo).all()
    return produtos, cursos


def _validar(form, produtos, cursos):
    return validar_promocao(
        form,
        {p.id: p.preco_centavos for p in produtos},
        {c.id: c.valor_centavos for c in cursos},
    )


def _aplicar(promo, dados, produtos, cursos):
    promo.nome = dados["nome"]
    promo.tipo = dados["tipo"]
    promo.percentual = dados["percentual"]
    promo.valor_centavos = dados["valor_centavos"]
    promo.inicio = dados["inicio"]
    promo.fim = dados["fim"]
    promo.ativa = dados["ativa"]
    promo.produtos = [p for p in produtos if p.id in dados["produto_ids"]]
    promo.cursos = [c for c in cursos if c.id in dados["curso_ids"]]


def _valores_da_promocao(promo):
    return {
        "nome": promo.nome, "tipo": promo.tipo,
        "percentual_texto": str(promo.percentual or ""),
        "valor_texto": formatar_preco_input(promo.valor_centavos),
        "inicio_texto": formatar_data_hora_input(promo.inicio),
        "fim_texto": formatar_data_hora_input(promo.fim),
        "produto_ids": [p.id for p in promo.produtos], "curso_ids": [c.id for c in promo.cursos],
        "ativa": promo.ativa,
    }


@bp.route("/promocoes")
def promocoes_lista():
    promocoes = Promocao.query.order_by(Promocao.inicio.desc()).all()
    return render_template("admin/promocoes_lista.html", promocoes=promocoes)


@bp.route("/promocoes/nova", methods=["GET", "POST"])
def promocao_nova():
    produtos, cursos = _opcoes()
    valores = {"nome": "", "tipo": "percentual", "percentual_texto": "", "valor_texto": "",
               "inicio_texto": "", "fim_texto": "", "produto_ids": [], "curso_ids": [], "ativa": True}

    if request.method == "POST":
        dados, erros = _validar(request.form, produtos, cursos)
        valores = dados
        if not erros:
            promo = Promocao()
            _aplicar(promo, dados, produtos, cursos)
            db.session.add(promo)
            db.session.commit()
            flash(f"Promoção “{promo.nome}” criada.", "ok")
            return redirect(url_for("admin.promocoes_lista"))
        for erro in erros:
            flash(erro, "erro")

    return render_template("admin/promocao_form.html", promocao=None, valores=valores,
                           produtos=produtos, cursos=cursos)


@bp.route("/promocoes/<int:promocao_id>/editar", methods=["GET", "POST"])
def promocao_editar(promocao_id):
    promo = db.get_or_404(Promocao, promocao_id)
    produtos, cursos = _opcoes()
    valores = _valores_da_promocao(promo)

    if request.method == "POST":
        dados, erros = _validar(request.form, produtos, cursos)
        valores = dados
        if not erros:
            _aplicar(promo, dados, produtos, cursos)
            db.session.commit()
            flash("Promoção salva.", "ok")
            return redirect(url_for("admin.promocoes_lista"))
        for erro in erros:
            flash(erro, "erro")

    return render_template("admin/promocao_form.html", promocao=promo, valores=valores,
                           produtos=produtos, cursos=cursos)


@bp.route("/promocoes/<int:promocao_id>/alternar", methods=["POST"])
def promocao_alternar(promocao_id):
    promo = db.get_or_404(Promocao, promocao_id)
    promo.ativa = not promo.ativa
    db.session.commit()
    flash(f"Promoção “{promo.nome}” {'ativada' if promo.ativa else 'desativada'}.", "ok")
    return redirect(url_for("admin.promocoes_lista"))


@bp.route("/promocoes/<int:promocao_id>/excluir", methods=["POST"])
def promocao_excluir(promocao_id):
    promo = db.get_or_404(Promocao, promocao_id)
    nome = promo.nome
    # Pedidos antigos não mudam: o item do pedido guarda o preço pago e o original
    db.session.delete(promo)
    db.session.commit()
    flash(f"Promoção “{nome}” excluída.", "ok")
    return redirect(url_for("admin.promocoes_lista"))
