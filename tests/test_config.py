"""Configuração da loja: WhatsApp e nome do site saem do .env, nunca escritos à mão."""
import re
from pathlib import Path

import pytest

from app.utils import whatsapp_link

PASTA_TEMPLATES = Path(__file__).resolve().parent.parent / "app" / "templates"
NUMERO_TESTE = "5511000000000"


@pytest.fixture()
def numero_teste(app):
    # Número diferente do real: prova que o link vem da configuração, não do código
    app.config["WHATSAPP_NUMBER"] = NUMERO_TESTE
    return NUMERO_TESTE


def test_whatsapp_link_usa_numero_da_configuracao(app, numero_teste):
    with app.test_request_context():
        assert whatsapp_link() == f"https://wa.me/{numero_teste}"


def test_whatsapp_link_codifica_a_mensagem(app, numero_teste):
    with app.test_request_context():
        link = whatsapp_link("Olá, Julia!")
    assert link == f"https://wa.me/{numero_teste}?text=Ol%C3%A1%2C%20Julia%21"


def test_nenhum_template_tem_link_de_whatsapp_escrito_a_mao():
    # Link escrito à mão não muda quando o número do .env muda: use whatsapp_link()
    padrao = re.compile(r"wa\.me/|api\.whatsapp\.com|web\.whatsapp\.com")
    culpados = [
        f"{arquivo.relative_to(PASTA_TEMPLATES)}:{numero}"
        for arquivo in PASTA_TEMPLATES.rglob("*.html")
        for numero, linha in enumerate(arquivo.read_text(encoding="utf-8").splitlines(), 1)
        if padrao.search(linha)
    ]
    assert culpados == [], f"Troque por {{{{ whatsapp_link() }}}}: {culpados}"


@pytest.mark.parametrize("rota", ["/", "/sobre", "/servicos", "/cursos"])
def test_paginas_so_linkam_o_whatsapp_configurado(client, catalogo, numero_teste, rota):
    html = client.get(rota).get_data(as_text=True)
    numeros = set(re.findall(r"wa\.me/(\d+)", html))
    assert numeros == {numero_teste}


def test_site_name_vem_da_configuracao(app, client):
    app.config["SITE_NAME"] = "Ateliê de Teste"
    html = client.get("/sobre").get_data(as_text=True)
    assert "<title>Sobre nós · Ateliê de Teste</title>" in html
