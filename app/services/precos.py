"""Preço final de peças e cursos: o ÚNICO lugar que aplica promoção.

Vitrine, página da peça, cursos, carrinho e checkout chamam estas funções, então o
cliente vê e paga sempre o mesmo valor.

Regras:
- vale promoção ativa e dentro do período (início <= agora < fim);
- duas promoções no mesmo item: vale a de menor preço final;
- desconto que zeraria (ou passaria) o preço é ignorado (proteção extra além da validação);
- curso "sob consulta" (sem valor) nunca tem promoção.
"""
from collections import namedtuple
from datetime import datetime, timezone

from flask import has_request_context, request
from sqlalchemy.orm import selectinload

from ..models import Promocao


class Preco(namedtuple("Preco", "original final promocao")):
    __slots__ = ()

    @property
    def tem_desconto(self):
        return self.promocao is not None

    @property
    def selo(self):
        return self.promocao.selo if self.promocao else ""


def _vigentes(agora=None):
    """{'produtos': {id: [promo]}, 'cursos': {id: [promo]}}. Uma consulta por requisição."""
    usar_cache = agora is None and has_request_context()
    if usar_cache and getattr(request, "_promocoes_vigentes", None) is not None:
        return request._promocoes_vigentes

    momento = agora or datetime.now(timezone.utc)
    promocoes = (
        Promocao.query.filter(Promocao.ativa.is_(True), Promocao.inicio <= momento, Promocao.fim > momento)
        .options(selectinload(Promocao.produtos), selectinload(Promocao.cursos))
        .all()
    )
    mapa = {"produtos": {}, "cursos": {}}
    for promo in promocoes:
        for produto in promo.produtos:
            mapa["produtos"].setdefault(produto.id, []).append(promo)
        for curso in promo.cursos:
            mapa["cursos"].setdefault(curso.id, []).append(promo)

    if usar_cache:
        # No objeto da requisição (e não em g): nos testes o g dura o teste inteiro
        request._promocoes_vigentes = mapa
    return mapa


def _melhor(original, promocoes):
    candidatos = [(promo.aplicar(original), promo) for promo in promocoes]
    validos = [(final, promo) for final, promo in candidatos if 0 < final < original]
    if not validos:
        return Preco(original, original, None)
    final, promo = min(validos, key=lambda par: (par[0], par[1].id))
    return Preco(original, final, promo)


def preco_produto(produto, agora=None):
    return _melhor(produto.preco_centavos, _vigentes(agora)["produtos"].get(produto.id, []))


def preco_curso(curso, agora=None):
    if curso.valor_centavos is None:
        return Preco(None, None, None)
    return _melhor(curso.valor_centavos, _vigentes(agora)["cursos"].get(curso.id, []))
