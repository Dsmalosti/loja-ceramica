"""Fotos de produtos: validação e gravação em disco.

Todo o armazenamento passa por aqui. Quando a loja for para o servidor (onde a
pasta de uploads pode ser apagada a cada deploy), é só trocar `gravar_imagem` e
`remover_imagem` por uma versão que usa Cloudinary ou S3; o resto do código não
muda, porque guarda apenas o "caminho" devolvido por `gravar_imagem`.
"""
import os
import uuid

from flask import current_app

TAMANHO_MAXIMO = 5 * 1024 * 1024  # por foto
MAX_IMAGENS_POR_PRODUTO = 8
SUBPASTA = "produtos"
PREFIXO = "uploads/produtos/"  # caminho guardado no banco, relativo a static/


class ImagemInvalida(Exception):
    """A foto enviada não pode ser aceita (a mensagem já é para mostrar à pessoa)."""


def _tipo_pelo_conteudo(conteudo):
    """Descobre o tipo pelos primeiros bytes, sem confiar no nome nem no tipo enviado."""
    if conteudo.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if conteudo.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if len(conteudo) >= 12 and conteudo[:4] == b"RIFF" and conteudo[8:12] == b"WEBP":
        return ".webp"
    return None


def preparar_imagem(arquivo):
    """Valida um arquivo enviado (FileStorage). Devolve (conteudo, extensao).

    A extensão vem do conteúdo real do arquivo: um .html renomeado para .jpg é
    recusado, e nenhum SVG/HTML chega a ser servido pelo site.
    """
    nome = (arquivo.filename or "foto")[:60]
    conteudo = arquivo.stream.read(TAMANHO_MAXIMO + 1)
    if not conteudo:
        raise ImagemInvalida(f"{nome}: o arquivo está vazio.")
    if len(conteudo) > TAMANHO_MAXIMO:
        raise ImagemInvalida(f"{nome}: a foto passa de 5 MB. Reduza o tamanho e envie de novo.")
    extensao = _tipo_pelo_conteudo(conteudo)
    if extensao is None:
        raise ImagemInvalida(f"{nome}: envie uma foto em JPG, PNG ou WEBP.")
    return conteudo, extensao


def gravar_imagem(conteudo, extensao):
    """Grava os bytes com um nome aleatório e devolve o caminho para guardar no banco."""
    pasta = os.path.join(current_app.config["UPLOAD_DIR"], SUBPASTA)
    os.makedirs(pasta, exist_ok=True)
    nome = uuid.uuid4().hex + extensao
    with open(os.path.join(pasta, nome), "wb") as arquivo:
        arquivo.write(conteudo)
    return PREFIXO + nome


def remover_imagem(caminho):
    """Apaga o arquivo de uma foto gravada por `gravar_imagem`.

    Ignora URLs externas e qualquer caminho fora da pasta de produtos.
    """
    if not caminho or not caminho.startswith(PREFIXO):
        return
    nome = caminho[len(PREFIXO):]
    if not nome or nome != os.path.basename(nome) or "\\" in nome:
        return
    try:
        os.remove(os.path.join(current_app.config["UPLOAD_DIR"], SUBPASTA, nome))
    except OSError:
        pass
