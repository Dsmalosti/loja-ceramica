import io
import os

import pytest
from flask import Flask
from werkzeug.datastructures import FileStorage

from app.services.imagens import (
    PREFIXO,
    TAMANHO_MAXIMO,
    ImagemInvalida,
    gravar_imagem,
    preparar_imagem,
    remover_imagem,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"dados-da-imagem"
JPG = b"\xff\xd8\xff\xe0" + b"dados-da-imagem"
WEBP = b"RIFF" + b"\x10\x00\x00\x00" + b"WEBP" + b"dados"


def arquivo(conteudo, nome="foto.jpg"):
    return FileStorage(stream=io.BytesIO(conteudo), filename=nome)


@pytest.fixture()
def pasta_de_uploads(tmp_path):
    """Contexto Flask mínimo (sem banco) só com a pasta de uploads."""
    app = Flask(__name__)
    app.config["UPLOAD_DIR"] = str(tmp_path)
    with app.app_context():
        yield tmp_path


@pytest.mark.parametrize(
    "conteudo, extensao", [(PNG, ".png"), (JPG, ".jpg"), (WEBP, ".webp")]
)
def test_aceita_pelo_conteudo_e_ignora_o_nome(conteudo, extensao):
    # O nome diz .gif, mas quem manda é o conteúdo real
    assert preparar_imagem(arquivo(conteudo, "qualquer.gif")) == (conteudo, extensao)


@pytest.mark.parametrize(
    "conteudo, nome",
    [
        (b"<html><script>alert(1)</script></html>", "pagina.jpg"),
        (b"<svg xmlns='http://www.w3.org/2000/svg'></svg>", "desenho.png"),
        (b"GIF89a....", "animacao.gif"),
        (b"%PDF-1.4", "arquivo.png"),
        (b"RIFF\x00\x00\x00\x00WAVE", "audio.webp"),
    ],
)
def test_recusa_o_que_nao_e_foto_mesmo_com_extensao_de_foto(conteudo, nome):
    with pytest.raises(ImagemInvalida):
        preparar_imagem(arquivo(conteudo, nome))


def test_recusa_vazio():
    with pytest.raises(ImagemInvalida, match="vazio"):
        preparar_imagem(arquivo(b""))


def test_recusa_acima_de_5mb_e_aceita_no_limite():
    grande = PNG + b"0" * (TAMANHO_MAXIMO - len(PNG) + 1)
    with pytest.raises(ImagemInvalida, match="5 MB"):
        preparar_imagem(arquivo(grande))

    no_limite = PNG + b"0" * (TAMANHO_MAXIMO - len(PNG))
    assert preparar_imagem(arquivo(no_limite))[1] == ".png"


def test_mensagem_de_erro_corta_nome_muito_longo():
    with pytest.raises(ImagemInvalida) as erro:
        preparar_imagem(arquivo(b"texto", "a" * 300 + ".jpg"))
    assert len(str(erro.value)) < 150


def test_grava_com_nome_aleatorio_e_remove(pasta_de_uploads):
    caminho = gravar_imagem(PNG, ".png")
    assert caminho.startswith(PREFIXO) and caminho.endswith(".png")

    gravado = pasta_de_uploads / "produtos" / caminho[len(PREFIXO):]
    assert gravado.read_bytes() == PNG

    assert gravar_imagem(PNG, ".png") != caminho  # nunca repete nome

    remover_imagem(caminho)
    assert not gravado.exists()
    remover_imagem(caminho)  # remover duas vezes não dá erro


def test_remover_ignora_url_externa_e_caminhos_perigosos(pasta_de_uploads):
    de_fora = pasta_de_uploads / "segredo.txt"
    de_fora.write_text("não apague")

    for caminho in [
        "https://exemplo.com/foto.jpg",
        PREFIXO + "../segredo.txt",
        PREFIXO + "..\\segredo.txt",
        "uploads/produtos/../../segredo.txt",
        "segredo.txt",
        PREFIXO,
        "",
        None,
    ]:
        remover_imagem(caminho)

    assert de_fora.read_text() == "não apague"
    assert os.path.isdir(pasta_de_uploads)
