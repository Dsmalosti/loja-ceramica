"""[back/seguranca-auditoria] Correções de backend da auditoria de 20/11/2026 (docs/auditoria/2026-11-20.md)."""
import re

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


# ---------- 2. Cabeçalhos de segurança e cache dos estáticos ----------

def test_toda_resposta_tem_cabecalhos_de_seguranca(client):
    for url in ("/", "/entrar", "/robots.txt", "/pagina-que-nao-existe"):
        h = client.get(url).headers
        assert h["X-Frame-Options"] == "DENY"
        assert h["X-Content-Type-Options"] == "nosniff"
        assert h["Referrer-Policy"] == "strict-origin-when-cross-origin"
        csp = h["Content-Security-Policy"]
        assert "script-src 'self';" in csp and "frame-ancestors 'none'" in csp and "object-src 'none'" in csp
        assert "unsafe-inline" not in csp and "unsafe-eval" not in csp


def test_csp_libera_so_os_servicos_que_o_site_usa(client):
    csp = client.get("/").headers["Content-Security-Policy"]
    assert "https://fonts.googleapis.com" in csp and "https://fonts.gstatic.com" in csp
    assert "connect-src 'self' https://viacep.com.br" in csp
    assert "https://*.mercadopago.com.br" in csp  # o checkout redireciona para lá


def test_hsts_so_em_producao(client):
    assert "Strict-Transport-Security" not in client.get("/").headers
    from app.seguranca import politica_de_conteudo
    assert "upgrade-insecure-requests" in politica_de_conteudo(producao=True)
    assert "upgrade-insecure-requests" not in politica_de_conteudo(producao=False)


def test_hsts_ligado_com_app_env_producao(monkeypatch):
    from app import create_app
    monkeypatch.setenv("SECRET_KEY", "chave-de-teste-producao")
    app = create_app("production")
    with app.test_request_context():
        resposta = app.process_response(app.response_class("ok"))
    assert resposta.headers["Strict-Transport-Security"].startswith("max-age=15552000")


def test_html_nao_tem_script_nem_estilo_em_linha(client):
    # Com a CSP sem 'unsafe-inline', qualquer um destes deixaria de funcionar
    for url in ("/", "/loja/", "/cursos", "/servicos", "/sobre", "/entrar", "/cadastro", "/privacidade"):
        html = client.get(url).get_data(as_text=True)
        assert not re.search(r"<script(?![^>]*\b(src|type=\"application/ld\+json\"))", html), url
        assert not re.search(r"\son[a-z]+=", html), url
        assert ' style="' not in html and "javascript:" not in html, url


def test_estaticos_ganham_versao_que_muda_com_o_arquivo(app, client, tmp_path):
    html = client.get("/").get_data(as_text=True)
    assert re.search(r'/static/css/style\.css\?v=[0-9a-f]{10}"', html)
    assert re.search(r'/static/js/site\.js\?v=[0-9a-f]{10}"', html)
    from app import estaticos
    arquivo = tmp_path / "x.css"
    arquivo.write_text("a{}")
    v1 = estaticos._impressao(str(arquivo), 1)
    arquivo.write_text("b{}")
    assert estaticos._impressao(str(arquivo), 2) != v1


def test_arquivo_inexistente_sai_sem_versao(app):
    from flask import url_for
    with app.test_request_context():
        assert url_for("static", filename="nao/existe.css") == "/static/nao/existe.css"


def test_producao_guarda_estaticos_por_um_ano():
    from config import ProductionConfig
    assert ProductionConfig.SEND_FILE_MAX_AGE_DEFAULT == 365 * 24 * 3600

