import unicodedata

from sqlalchemy.orm import contains_eager, selectinload

from ..models import Category, Product
from ..utils import slugify

# [back/duas-lojas] Quantos itens cada faixa da Início mostra (antes: 4, de todos os produtos)
LIMITE_VITRINE = 8
BUSCA_MAXIMA = 80


def slug_unico(modelo, texto, ignorar_id=None):
    """Gera um slug que ainda não existe na tabela: 'caneca' -> 'caneca-2' se já houver."""
    base = (slugify(texto) or "item")[:100]
    slug, numero = base, 2
    while True:
        consulta = modelo.query.filter_by(slug=slug)
        if ignorar_id is not None:
            consulta = consulta.filter(modelo.id != ignorar_id)
        if consulta.first() is None:
            return slug
        slug = f"{base}-{numero}"
        numero += 1


# [back/duas-lojas] Consultas da loja. Antes ficavam repetidas em shop.py e public.py, sem separar por loja.
def _ativos_da_loja(loja):
    return (
        Product.query.join(Category)
        .options(contains_eager(Product.categoria), selectinload(Product.imagens))
        .filter(Product.ativo.is_(True), Category.ativa.is_(True), Category.loja == loja)
    )


def produtos_da_loja(loja, categoria=None):
    consulta = _ativos_da_loja(loja)
    if categoria is not None:
        consulta = consulta.filter(Product.categoria_id == categoria.id)
    # [back/painel-julia] Destaques primeiro. Antes: só ordem alfabética.
    return consulta.order_by(Product.destaque.desc(), Product.nome).all()


def novidades_da_loja(loja, limite=LIMITE_VITRINE):
    # [back/painel-julia] Destaques da Julia primeiro, depois os mais novos. Antes: só os mais novos.
    return (_ativos_da_loja(loja)
            .order_by(Product.destaque.desc(), Product.criado_em.desc(), Product.id.desc())
            .limit(limite).all())


def _sem_acento(texto):
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c)).casefold()


def filtrar_por_busca(produtos, busca):
    """Mantém quem tem todas as palavras no nome, na descrição ou na categoria.

    Feito em Python para "ceramica" achar "Cerâmica" igual no SQLite e no Postgres, sem
    extensão no banco. A lista já vem inteira da loja, e o catálogo é de um ateliê.
    """
    termos = _sem_acento(busca).split()

    def combina(produto):
        alvo = _sem_acento(f"{produto.nome} {produto.descricao} {produto.categoria.nome}")
        return all(termo in alvo for termo in termos)

    return [produto for produto in produtos if combina(produto)]
