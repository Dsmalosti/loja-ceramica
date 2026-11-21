"""[back/painel-julia] Muda a ordem de uma lista (fotos de produto e de curso).

A lista chega já ordenada pela coluna `ordem`. A primeira é a capa: é a foto que aparece na loja,
nos cartões e no compartilhamento. Depois de mover, a coluna é renumerada de 0 em diante.
"""

ACOES = ("capa", "antes", "depois")


def mover(itens, alvo, acao):
    """Move `alvo` dentro de `itens`. Ação desconhecida ou impossível (antes da primeira) não muda nada."""
    lista = list(itens)
    posicao = lista.index(alvo)
    if acao == "capa":
        lista.insert(0, lista.pop(posicao))
    elif acao == "antes" and posicao > 0:
        lista[posicao - 1], lista[posicao] = lista[posicao], lista[posicao - 1]
    elif acao == "depois" and posicao < len(lista) - 1:
        lista[posicao + 1], lista[posicao] = lista[posicao], lista[posicao + 1]
    for numero, item in enumerate(lista):
        item.ordem = numero
    return lista
