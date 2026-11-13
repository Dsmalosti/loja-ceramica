"""Carrinho de compras guardado na sessão (cookie assinado do Flask).

Na sessão ficam só `{id do produto: quantidade}`. Preço, nome e estoque são sempre
lidos do banco ao exibir o carrinho, então nada que venha do navegador define preço.
"""
from collections import namedtuple

CHAVE = "carrinho"
MAX_POR_ITEM = 99

Linha = namedtuple("Linha", "produto quantidade subtotal_centavos")


def vendavel(produto):
    """Produto que pode ir para o carrinho: ativo, categoria ativa e com estoque."""
    return bool(produto and produto.ativo and produto.categoria.ativa and produto.estoque > 0)


def limitar(quantidade, estoque):
    """Quantidade permitida: nunca acima do estoque nem de MAX_POR_ITEM, nunca negativa."""
    return max(0, min(quantidade, estoque, MAX_POR_ITEM))


def ler(sessao):
    """Itens da sessão como {id: quantidade}, ignorando qualquer valor estranho."""
    bruto = sessao.get(CHAVE)
    if not isinstance(bruto, dict):
        return {}
    itens = {}
    for chave, valor in bruto.items():
        try:
            produto_id, quantidade = int(chave), int(valor)
        except (TypeError, ValueError):
            continue
        if produto_id > 0 and quantidade > 0:
            itens[produto_id] = min(quantidade, MAX_POR_ITEM)
    return itens


def _gravar(sessao, itens):
    sessao[CHAVE] = {str(produto_id): quantidade for produto_id, quantidade in itens.items()}
    sessao.modified = True


def quantidade_total(sessao):
    return sum(ler(sessao).values())


def adicionar(sessao, produto, quantidade=1):
    """Soma ao carrinho. Devolve (situacao, quantidade_final).

    situacao: 'ok', 'limitado' (passou do estoque e foi reduzido) ou 'indisponivel'.
    """
    if not vendavel(produto):
        return "indisponivel", 0
    itens = ler(sessao)
    desejada = itens.get(produto.id, 0) + quantidade
    final = limitar(desejada, produto.estoque)
    itens[produto.id] = final
    _gravar(sessao, itens)
    return ("ok" if final == desejada else "limitado"), final


def definir(sessao, produto, quantidade):
    """Troca a quantidade de um item (0 remove). Mesmo retorno de `adicionar`."""
    itens = ler(sessao)
    if quantidade <= 0:
        itens.pop(produto.id, None)
        _gravar(sessao, itens)
        return "ok", 0
    if not vendavel(produto):
        itens.pop(produto.id, None)
        _gravar(sessao, itens)
        return "indisponivel", 0
    final = limitar(quantidade, produto.estoque)
    itens[produto.id] = final
    _gravar(sessao, itens)
    return ("ok" if final == quantidade else "limitado"), final


def remover(sessao, produto_id):
    itens = ler(sessao)
    itens.pop(produto_id, None)
    _gravar(sessao, itens)


def limpar(sessao):
    sessao.pop(CHAVE, None)


def detalhar(sessao):
    """Monta o carrinho para exibir: (linhas, total_centavos, avisos).

    Corrige a sessão: remove produto que sumiu/foi desativado e reduz quantidade que
    passou do estoque, explicando cada mudança em `avisos`.
    """
    # Importados aqui para que as funções puras acima possam ser testadas sem banco
    from sqlalchemy.orm import joinedload

    from ..models import Product

    itens = ler(sessao)
    if not itens:
        if CHAVE in sessao:
            limpar(sessao)
        return [], 0, []

    produtos = {
        p.id: p
        for p in Product.query.options(joinedload(Product.imagens), joinedload(Product.categoria))
        .filter(Product.id.in_(itens))
        .all()
    }

    linhas, avisos, corrigidos = [], [], {}
    for produto_id, quantidade in itens.items():
        produto = produtos.get(produto_id)
        if not vendavel(produto):
            nome = f"“{produto.nome}”" if produto else "Um produto"
            avisos.append(f"{nome} não está mais disponível e saiu do carrinho.")
            continue
        final = limitar(quantidade, produto.estoque)
        if final < quantidade:
            avisos.append(f"“{produto.nome}”: só temos {final} em estoque, ajustamos a quantidade.")
        corrigidos[produto_id] = final
        linhas.append(Linha(produto, final, produto.preco_centavos * final))

    if corrigidos != itens:
        _gravar(sessao, corrigidos)

    linhas.sort(key=lambda linha: linha.produto.nome.lower())
    return linhas, sum(linha.subtotal_centavos for linha in linhas), avisos
