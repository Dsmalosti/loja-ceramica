"""Fotos em produção no Cloudinary (a Vercel apaga arquivos enviados a cada deploy).

- STORAGE_FOTOS=local (padrão, dev e testes) grava em disco como antes;
- STORAGE_FOTOS=cloudinary sobe por upload ASSINADO e guarda a URL no mesmo campo `caminho`;
- image_url() pede ao Cloudinary WebP/AVIF no tamanho da tela (f_auto,q_auto,w_...).
O segredo da API nunca sai do servidor: só a assinatura vai na requisição.
"""
import hashlib
import io

import pytest
from werkzeug.datastructures import FileStorage

from app.models import Product, ProductImage
from app.services import imagens
from app.services.imagens import ErroArmazenamento, assinar_cloudinary, public_id_da_url
from app.utils import image_url

JPG = b"\xff\xd8\xff\xe0" + b"dados-da-imagem"
NUVEM = "loja-teste"
SEGREDO = "segredo-cloudinary-de-teste"
BASE = f"https://res.cloudinary.com/{NUVEM}/image/upload/"


class CloudinaryFalso:
    def __init__(self):
        self.chamadas = []
        self.fora_do_ar = False
        self.url_resposta = None

    def __call__(self, acao, campos, arquivo=None):
        self.chamadas.append({"acao": acao, "campos": dict(campos), "arquivo": arquivo})
        if self.fora_do_ar:
            raise ErroArmazenamento("Não conseguimos enviar a foto agora. Tente de novo em alguns minutos.")
        if acao == "upload":
            return {"public_id": campos["public_id"], "version": 1731600000, "format": "jpg",
                    "secure_url": self.url_resposta or f"{BASE}v1731600000/{campos['public_id']}.jpg"}
        return {"result": "ok"}


@pytest.fixture()
def nuvem(app, monkeypatch):
    app.config.update(STORAGE_FOTOS="cloudinary", CLOUDINARY_CLOUD_NAME=NUVEM, CLOUDINARY_API_KEY="123456",
                      CLOUDINARY_API_SECRET=SEGREDO, CLOUDINARY_PASTA="julia-malosti/produtos")
    falso = CloudinaryFalso()
    monkeypatch.setattr(imagens, "_post_cloudinary", falso)
    return falso


# ---------- Assinatura: exemplos oficiais da documentação do Cloudinary ----------

def test_assinatura_bate_com_o_exemplo_oficial_simples():
    assert assinar_cloudinary({"timestamp": 1315060510}, "abcd") == "a21ad0f63beb4de2e5575204b79ab90bffb02c10"


def test_assinatura_bate_com_o_exemplo_oficial_completo_e_ignora_campos_de_fora():
    params = {"timestamp": 1315060510, "public_id": "sample_image", "eager": "w_400,h_300,c_pad|w_260,h_200,c_crop",
              "file": "x", "api_key": "1234", "cloud_name": "demo", "resource_type": "image"}
    assert assinar_cloudinary(params, "abcd") == "bfd09f95f331f558cbd1320e67aa8d488770583e"


# ---------- Upload ----------

def test_sobe_assinado_e_guarda_a_url(app, nuvem):
    with app.test_request_context():
        caminho = imagens.gravar_imagem(JPG, ".jpg")
    chamada = nuvem.chamadas[0]
    campos = chamada["campos"]
    assert chamada["acao"] == "upload" and chamada["arquivo"][1] == JPG
    assert campos["public_id"].startswith("julia-malosti/produtos/") and campos["api_key"] == "123456"
    assinados = {k: v for k, v in campos.items() if k not in ("api_key", "signature")}
    assert campos["signature"] == assinar_cloudinary(assinados, SEGREDO)
    assert SEGREDO not in str(chamada)  # o segredo nunca vai na requisição
    assert caminho == f"{BASE}v1731600000/{campos['public_id']}.jpg"


def test_nomes_sao_aleatorios(app, nuvem):
    with app.test_request_context():
        imagens.gravar_imagem(JPG, ".jpg")
        imagens.gravar_imagem(JPG, ".jpg")
    ids = [c["campos"]["public_id"] for c in nuvem.chamadas]
    assert ids[0] != ids[1]


def test_url_de_resposta_estranha_e_recusada(app, nuvem):
    nuvem.url_resposta = "https://evil.example.com/foto.jpg"
    with app.test_request_context(), pytest.raises(ErroArmazenamento):
        imagens.gravar_imagem(JPG, ".jpg")


def test_sem_credenciais_nao_envia(app, nuvem):
    app.config["CLOUDINARY_API_SECRET"] = ""
    with app.test_request_context(), pytest.raises(ErroArmazenamento):
        imagens.gravar_imagem(JPG, ".jpg")
    assert nuvem.chamadas == []


def test_falha_de_rede_vira_erro_amigavel_sem_segredo(app, monkeypatch):
    app.config.update(STORAGE_FOTOS="cloudinary", CLOUDINARY_CLOUD_NAME=NUVEM, CLOUDINARY_API_KEY="123456",
                      CLOUDINARY_API_SECRET=SEGREDO, CLOUDINARY_API_URL="http://127.0.0.1:9")  # porta fechada
    with app.test_request_context(), pytest.raises(ErroArmazenamento) as erro:
        imagens.gravar_imagem(JPG, ".jpg")
    assert SEGREDO not in str(erro.value)


# ---------- Remoção ----------

def test_remove_pelo_public_id(app, nuvem):
    with app.test_request_context():
        imagens.remover_imagem(f"{BASE}v1731600000/julia-malosti/produtos/abc123.jpg")
    chamada = nuvem.chamadas[0]
    assert chamada["acao"] == "destroy" and chamada["campos"]["public_id"] == "julia-malosti/produtos/abc123"
    assinados = {k: v for k, v in chamada["campos"].items() if k not in ("api_key", "signature")}
    assert chamada["campos"]["signature"] == assinar_cloudinary(assinados, SEGREDO)


@pytest.mark.parametrize("caminho", [
    "https://res.cloudinary.com/outra-conta/image/upload/v1/julia-malosti/produtos/abc.jpg",  # outra conta
    f"{BASE}v1/outra-pasta/abc.jpg",                                                           # fora da pasta
    f"{BASE}v1/julia-malosti/produtos/../../tudo.jpg",                                         # truque de caminho
    "uploads/produtos/abc.jpg", "https://exemplo.com/foto.jpg", "",
])
def test_nao_apaga_o_que_nao_e_nosso(app, nuvem, caminho):
    with app.test_request_context():
        imagens.remover_imagem(caminho)
    assert [c for c in nuvem.chamadas if c["acao"] == "destroy"] == []


def test_falha_ao_apagar_nao_quebra(app, nuvem):
    nuvem.fora_do_ar = True
    with app.test_request_context():
        imagens.remover_imagem(f"{BASE}v1/julia-malosti/produtos/abc.jpg")  # não lança


def test_public_id_da_url():
    assert public_id_da_url(f"{BASE}v123/julia-malosti/produtos/abc.webp", NUVEM, "julia-malosti/produtos") == \
        "julia-malosti/produtos/abc"
    assert public_id_da_url(f"{BASE}julia-malosti/produtos/abc.jpg", NUVEM, "julia-malosti/produtos") == \
        "julia-malosti/produtos/abc"
    assert public_id_da_url("https://x.com/a.jpg", NUVEM, "julia-malosti/produtos") is None


# ---------- Entrega leve (WebP/AVIF no tamanho certo) ----------

def test_image_url_pede_formato_e_tamanho_ao_cloudinary(app):
    url = f"{BASE}v1731600000/julia-malosti/produtos/abc.jpg"
    with app.test_request_context():
        assert image_url(url, 600) == f"{BASE}f_auto,q_auto,c_limit,w_600/v1731600000/julia-malosti/produtos/abc.jpg"
        assert image_url(url) == f"{BASE}f_auto,q_auto,c_limit,w_1200/v1731600000/julia-malosti/produtos/abc.jpg"
        assert image_url("uploads/produtos/a.jpg", 600) == "/static/uploads/produtos/a.jpg"  # local: igual antes
        assert image_url("https://exemplo.com/a.jpg", 600) == "https://exemplo.com/a.jpg"


# ---------- Pelo painel ----------

def form_produto(**extra):
    dados = {"nome": "Tigela nova", "descricao": "", "preco": "80,00", "estoque": "2", "ativo": "on"}
    dados.update(extra)
    return dados


def test_painel_sobe_foto_no_cloudinary_e_a_loja_mostra_leve(client_admin, catalogo, nuvem):
    categoria = Product.query.first().categoria_id
    foto = (io.BytesIO(JPG), "tigela.jpg")
    client_admin.post("/admin/produtos/novo", data={**form_produto(categoria_id=str(categoria)), "imagens": foto},
                      content_type="multipart/form-data")
    imagem = ProductImage.query.one()
    assert imagem.caminho.startswith(BASE)
    html = client_admin.get("/loja/").get_data(as_text=True)
    assert "f_auto,q_auto,c_limit,w_600" in html


def test_cloudinary_fora_do_ar_nao_cria_produto_pela_metade(client_admin, catalogo, nuvem):
    nuvem.fora_do_ar = True
    categoria = Product.query.first().categoria_id
    html = client_admin.post("/admin/produtos/novo",
                             data={**form_produto(categoria_id=str(categoria)), "imagens": (io.BytesIO(JPG), "t.jpg")},
                             content_type="multipart/form-data", follow_redirects=True).get_data(as_text=True)
    assert Product.query.filter_by(nome="Tigela nova").first() is None and ProductImage.query.count() == 0
    assert "Tente de novo" in html


def test_se_a_segunda_foto_falha_a_primeira_e_apagada(client_admin, catalogo, nuvem, monkeypatch):
    original = nuvem.__call__
    enviados = []

    def falha_na_segunda(acao, campos, arquivo=None):
        if acao == "upload":
            enviados.append(1)
            if len(enviados) == 2:
                raise ErroArmazenamento("Não conseguimos enviar a foto agora. Tente de novo em alguns minutos.")
        return original(acao, campos, arquivo)

    monkeypatch.setattr(imagens, "_post_cloudinary", falha_na_segunda)
    pid = Product.query.first().id
    client_admin.post(f"/admin/produtos/{pid}/imagens",
                      data={"imagens": [(io.BytesIO(JPG), "a.jpg"), (io.BytesIO(JPG), "b.jpg")]},
                      content_type="multipart/form-data")
    assert ProductImage.query.count() == 0
    assert [c["acao"] for c in nuvem.chamadas] == ["upload", "destroy"]  # a que subiu foi apagada
