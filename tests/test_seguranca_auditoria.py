"""[back/seguranca-auditoria] Correções de backend da auditoria de 20/11/2026 (docs/auditoria/2026-11-20.md)."""
from app.models import Product


# ---------- 1. Privacidade, termos, robots.txt e sitemap.xml ----------

def test_privacidade_e_termos_existem_e_sao_publicos(client):
    for url, titulo in (("/privacidade", "Política de privacidade"), ("/termos", "Termos de uso")):
        r = client.get(url)
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert titulo in html and "index, follow" in html


def test_privacidade_cita_os_servicos_que_recebem_dados(client):
    html = client.get("/privacidade").get_data(as_text=True)
    for servico in ("Mercado Pago", "Brevo", "Render", "Google"):
        assert servico in html
    assert "cartão" in html  # deixa claro que não guardamos cartão


def test_rodape_e_cadastro_levam_aos_termos(client):
    inicio = client.get("/").get_data(as_text=True)
    assert 'href="/privacidade"' in inicio and 'href="/termos"' in inicio
    cadastro = client.get("/cadastro").get_data(as_text=True)
    assert 'href="/termos"' in cadastro and 'href="/privacidade"' in cadastro


def test_checkout_avisa_dos_termos(client_cliente, catalogo):
    produto = Product.query.filter_by(slug="caneca-azul").one()
    client_cliente.post(f"/carrinho/adicionar/{produto.id}", data={"quantidade": 1})
    assert 'href="/termos"' in client_cliente.get("/checkout/").get_data(as_text=True)


def test_robots_bloqueia_telas_privadas_e_aponta_o_sitemap(client):
    r = client.get("/robots.txt")
    assert r.status_code == 200 and r.mimetype == "text/plain"
    texto = r.get_data(as_text=True)
    for privada in ("/admin/", "/conta/", "/carrinho/", "/checkout/"):
        assert f"Disallow: {privada}" in texto
    assert "Sitemap: https://loja.exemplo.test/sitemap.xml" in texto


def test_sitemap_lista_paginas_publicas_e_so_produtos_visiveis(client, catalogo):
    r = client.get("/sitemap.xml")
    assert r.status_code == 200 and r.mimetype == "application/xml"
    xml = r.get_data(as_text=True)
    for caminho in ("/", "/loja/", "/cursos", "/servicos", "/sobre", "/privacidade", "/termos"):
        assert f"<loc>https://loja.exemplo.test{caminho}</loc>" in xml
    assert "/loja/caneca-azul</loc>" in xml
    assert "caneca-oculta" not in xml  # produto desativado não vai para a busca
    assert "/admin" not in xml and "/conta" not in xml
