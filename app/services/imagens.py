"""Fotos de produtos: validação e gravação (disco local ou Cloudinary).

Todo o armazenamento passa por aqui. O resto do código guarda apenas o "caminho"
devolvido por `gravar_imagem`: um caminho em static/ (local) ou a URL do Cloudinary.
Quem escolhe é STORAGE_FOTOS no .env ("local" no dev; "cloudinary" em produção,
porque hospedagens em nuvem costumam apagar os arquivos enviados a cada deploy).

Cloudinary sem SDK: upload e remoção ASSINADOS (o segredo nunca sai do servidor,
só a assinatura vai na requisição). Docs: cloudinary.com/documentation/authentication_signatures
"""
import hashlib
import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
import uuid

from flask import current_app

log = logging.getLogger(__name__)

TAMANHO_MAXIMO = 5 * 1024 * 1024  # por foto
MAX_IMAGENS_POR_PRODUTO = 8
SUBPASTA = "produtos"
PREFIXO = "uploads/produtos/"  # caminho guardado no banco, relativo a static/


class ImagemInvalida(Exception):
    """A foto enviada não pode ser aceita (a mensagem já é para mostrar à pessoa)."""


class ErroArmazenamento(Exception):
    """Não deu para gravar no armazenamento externo (a mensagem já é para mostrar à pessoa)."""


MENSAGEM_FORA_DO_AR = "Não conseguimos enviar a foto agora. Tente de novo em alguns minutos."


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
    """Grava os bytes com um nome aleatório e devolve o caminho (ou URL) para guardar no banco."""
    if current_app.config.get("STORAGE_FOTOS") == "cloudinary":
        return _gravar_cloudinary(conteudo, extensao)
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
    if caminho and caminho.startswith("https://res.cloudinary.com/"):
        _remover_cloudinary(caminho)
        return
    if not caminho or not caminho.startswith(PREFIXO):
        return
    nome = caminho[len(PREFIXO):]
    if not nome or nome != os.path.basename(nome) or "\\" in nome:
        return
    try:
        os.remove(os.path.join(current_app.config["UPLOAD_DIR"], SUBPASTA, nome))
    except OSError:
        pass


# ---------- Cloudinary ----------

# Nunca entram no texto assinado (regra da documentação do Cloudinary)
_FORA_DA_ASSINATURA = {"file", "cloud_name", "resource_type", "api_key", "signature"}
_MIME = {".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


def assinar_cloudinary(params, segredo):
    """SHA-1 de "chave=valor&..." (ordem alfabética, sem os campos de fora) + segredo."""
    texto = "&".join(
        f"{chave}={params[chave]}"
        for chave in sorted(params)
        if chave not in _FORA_DA_ASSINATURA and params[chave] not in (None, "")
    )
    return hashlib.sha1((texto + segredo).encode()).hexdigest()


def _config_cloudinary():
    cfg = current_app.config
    nuvem, chave, segredo = (cfg.get("CLOUDINARY_CLOUD_NAME"), cfg.get("CLOUDINARY_API_KEY"),
                             cfg.get("CLOUDINARY_API_SECRET"))
    if not (nuvem and chave and segredo):
        log.error("STORAGE_FOTOS=cloudinary, mas faltam as credenciais do Cloudinary")
        raise ErroArmazenamento("O armazenamento de fotos não está configurado. Avise quem cuida do site.")
    return nuvem, chave, segredo, cfg.get("CLOUDINARY_PASTA", "julia-malosti/produtos").strip("/")


def _post_cloudinary(acao, campos, arquivo=None):
    """POST multipart na API do Cloudinary. Os testes trocam esta função por um Cloudinary falso."""
    cfg = current_app.config
    url = f"{cfg['CLOUDINARY_API_URL']}/{cfg['CLOUDINARY_CLOUD_NAME']}/image/{acao}"
    fronteira = uuid.uuid4().hex
    partes = []
    for nome, valor in campos.items():
        partes.append(f'--{fronteira}\r\nContent-Disposition: form-data; name="{nome}"\r\n\r\n{valor}\r\n'.encode())
    if arquivo:
        nome_arquivo, conteudo, tipo = arquivo
        partes.append(
            f'--{fronteira}\r\nContent-Disposition: form-data; name="file"; filename="{nome_arquivo}"\r\n'
            f"Content-Type: {tipo}\r\n\r\n".encode() + conteudo + b"\r\n"
        )
    partes.append(f"--{fronteira}--\r\n".encode())
    pedido = urllib.request.Request(url, data=b"".join(partes), method="POST",
                                    headers={"Content-Type": f"multipart/form-data; boundary={fronteira}"})
    try:
        with urllib.request.urlopen(pedido, timeout=20) as resposta:
            return json.loads(resposta.read().decode())
    except urllib.error.HTTPError as erro:
        log.error("Cloudinary respondeu HTTP %s em %s", erro.code, acao)  # sem corpo nem segredo no log
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as erro:
        log.error("Falha ao falar com o Cloudinary (%s): %s", acao, type(erro).__name__)
    raise ErroArmazenamento(MENSAGEM_FORA_DO_AR)


def _gravar_cloudinary(conteudo, extensao):
    nuvem, chave, segredo, pasta = _config_cloudinary()
    params = {
        "public_id": f"{pasta}/{uuid.uuid4().hex}",  # nome gerado no servidor, como no disco
        "timestamp": int(time.time()),
        "overwrite": "false",
        "allowed_formats": "jpg,png,webp",
    }
    campos = {**params, "api_key": chave, "signature": assinar_cloudinary(params, segredo)}
    resposta = _post_cloudinary("upload", campos, arquivo=("foto" + extensao, conteudo, _MIME[extensao]))
    url = str(resposta.get("secure_url") or "")
    # Só aceita URL da nossa conta: nada de gravar no banco um endereço qualquer
    if not url.startswith(f"https://res.cloudinary.com/{nuvem}/image/upload/"):
        log.error("Cloudinary devolveu uma URL inesperada")
        raise ErroArmazenamento(MENSAGEM_FORA_DO_AR)
    return url


def public_id_da_url(url, nuvem, pasta):
    """URL de entrega -> public_id, só se for da nossa conta e da nossa pasta. Senão None."""
    prefixo = f"https://res.cloudinary.com/{nuvem}/image/upload/"
    if not url or not url.startswith(prefixo):
        return None
    resto = re.sub(r"^v\d+/", "", url[len(prefixo):])
    public_id = re.sub(r"\.[A-Za-z0-9]+$", "", resto)
    # Só letras, números, _ - e /: sem ponto, então "../" (sair da pasta) nunca passa
    if not public_id.startswith(pasta.strip("/") + "/") or not re.fullmatch(r"[\w\-/]+", public_id):
        return None
    return public_id


def _remover_cloudinary(url):
    """Apaga do Cloudinary. Falha aqui não pode quebrar a exclusão do produto: só registra."""
    try:
        nuvem, chave, segredo, pasta = _config_cloudinary()
    except ErroArmazenamento:
        return
    public_id = public_id_da_url(url, nuvem, pasta)
    if public_id is None:
        return
    params = {"public_id": public_id, "timestamp": int(time.time()), "invalidate": "true"}
    try:
        _post_cloudinary("destroy", {**params, "api_key": chave, "signature": assinar_cloudinary(params, segredo)})
    except ErroArmazenamento:
        log.warning("Não deu para apagar %s do Cloudinary agora", public_id)
