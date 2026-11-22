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


# ---------- 3. Limite de tentativas e sessão nova no login ----------

def _entrar(client, senha, email="cliente@exemplo.com", ip="10.0.0.1"):
    return client.post("/entrar", data={"email": email, "senha": senha}, environ_base={"REMOTE_ADDR": ip})


def _logado(client):
    return client.get("/conta").status_code == 200


def test_cinco_senhas_erradas_bloqueiam_a_conta_por_15_minutos(client, criar_usuario):
    criar_usuario()
    for _ in range(5):
        assert _entrar(client, "errada").status_code == 200
    r = _entrar(client, "senha-segura-123")  # até a senha certa espera
    assert r.status_code == 429 and "Muitas tentativas" in r.get_data(as_text=True)
    assert not _logado(client)


def test_bloqueio_passa_depois_de_15_minutos(client, criar_usuario):
    from datetime import timedelta
    from app.extensions import db
    from app.models import TentativaAcesso
    criar_usuario()
    for _ in range(5):
        _entrar(client, "errada")
    for tentativa in TentativaAcesso.query.all():
        tentativa.criado_em = tentativa.criado_em - timedelta(minutes=16)
    db.session.commit()
    _entrar(client, "senha-segura-123")
    assert _logado(client)


def test_acertar_a_senha_zera_as_erradas_da_conta(client, criar_usuario):
    criar_usuario()
    for _ in range(4):
        _entrar(client, "errada")
    _entrar(client, "senha-segura-123")
    client.post("/sair")
    for _ in range(4):
        _entrar(client, "errada")
    _entrar(client, "senha-segura-123")
    assert _logado(client)


def test_bloqueio_de_uma_conta_nao_atinge_outra(client, criar_usuario):
    criar_usuario()
    criar_usuario(email="outra@exemplo.com")
    for _ in range(5):
        _entrar(client, "errada")
    _entrar(client, "senha-segura-123", email="outra@exemplo.com")
    assert _logado(client)


def test_muitas_contas_testadas_do_mesmo_ip_bloqueiam_o_ip(client, criar_usuario):
    criar_usuario()
    for i in range(20):
        _entrar(client, "errada", email=f"chute{i}@exemplo.com", ip="10.9.9.9")
    assert _entrar(client, "senha-segura-123", ip="10.9.9.9").status_code == 429
    _entrar(client, "senha-segura-123", ip="10.1.1.1")  # outro endereço segue entrando
    assert _logado(client)


def test_esqueci_a_senha_para_de_enviar_mas_responde_igual(client, criar_usuario, monkeypatch):
    from app.services import email
    enviados = []
    monkeypatch.setattr(email, "_requisicao", lambda corpo, chave: enviados.append(corpo) or 201)
    criar_usuario()
    respostas = []
    for _ in range(5):
        r = client.post("/esqueci-senha", data={"email": "cliente@exemplo.com"}, follow_redirects=True)
        respostas.append(r.get_data(as_text=True))
    assert len(enviados) == 3
    assert all("Se esse e-mail tiver conta" in html for html in respostas)


def test_cadastro_limitado_por_ip(client):
    for i in range(10):
        client.post("/cadastro", data={"nome": "Robô", "email": f"robo{i}@exemplo.com", "senha": "senha-segura-123",
                                       "confirmacao": "senha-segura-123"}, environ_base={"REMOTE_ADDR": "10.7.7.7"})
        client.post("/sair")
    r = client.post("/cadastro", data={"nome": "Robô", "email": "robo99@exemplo.com", "senha": "senha-segura-123",
                                       "confirmacao": "senha-segura-123"}, environ_base={"REMOTE_ADDR": "10.7.7.7"})
    assert r.status_code == 429
    from app.models import User
    assert User.query.filter_by(email="robo99@exemplo.com").first() is None


def test_tentativas_com_mais_de_um_dia_sao_apagadas(app):
    from datetime import timedelta
    from app.extensions import db
    from app.models import TentativaAcesso, agora
    from app.services import limite
    db.session.add(TentativaAcesso(chave="login:velha@exemplo.com", criado_em=agora() - timedelta(days=2)))
    db.session.commit()
    with app.test_request_context():
        limite.anotar("login:nova@exemplo.com")
    assert [t.chave for t in TentativaAcesso.query.all()] == ["login:nova@exemplo.com"]


def test_login_comeca_uma_sessao_nova(client, criar_usuario):
    criar_usuario()
    with client.session_transaction() as sessao:
        sessao["plantado_antes_do_login"] = "x"
    _entrar(client, "senha-segura-123")
    with client.session_transaction() as sessao:
        assert "plantado_antes_do_login" not in sessao
        assert sessao.get("_user_id")


def test_producao_le_o_ip_do_proxy(monkeypatch):
    from werkzeug.middleware.proxy_fix import ProxyFix
    from app import create_app
    monkeypatch.setenv("SECRET_KEY", "chave-de-teste-producao")
    assert isinstance(create_app("production").wsgi_app, ProxyFix)
    from config import TestingConfig
    assert not getattr(TestingConfig, "ATRAS_DE_PROXY", False)


# ---------- 4. Telefone no checkout ----------

def _sem_telefone():
    from app.extensions import db
    from app.models import User
    usuario = User.query.filter_by(email="cliente@exemplo.com").one()
    usuario.telefone = None
    db.session.commit()
    return usuario


def _ir_ao_resumo(client):
    produto = Product.query.filter_by(slug="caneca-azul").one()
    client.post(f"/carrinho/adicionar/{produto.id}", data={"quantidade": 1})
    html = client.get("/checkout/").get_data(as_text=True)
    return html, re.search(r'name="token" value="([^"]+)"', html).group(1)


def test_resumo_pede_o_whatsapp_ja_preenchido(client_cliente, catalogo):
    html, _ = _ir_ao_resumo(client_cliente)
    assert 'name="telefone"' in html and 'value="(12) 98888-7777"' in html and "required" in html


def test_sem_telefone_nao_fecha_o_pedido(client_cliente, catalogo):
    from app.models import Pedido
    _sem_telefone()
    _, token = _ir_ao_resumo(client_cliente)
    r = client_cliente.post("/checkout/confirmar", data={"token": token, "telefone": ""}, follow_redirects=True)
    assert "Informe um WhatsApp com DDD" in r.get_data(as_text=True)
    assert Pedido.query.count() == 0


def test_telefone_invalido_nao_fecha_o_pedido(client_cliente, catalogo):
    from app.models import Pedido
    _, token = _ir_ao_resumo(client_cliente)
    client_cliente.post("/checkout/confirmar", data={"token": token, "telefone": "123"})
    assert Pedido.query.count() == 0


def test_telefone_do_checkout_fica_salvo_na_conta(client_cliente, catalogo, monkeypatch):
    from app.models import Pedido
    from app.services import mercadopago
    monkeypatch.setattr(mercadopago, "criar_preferencia",
                        lambda pedido: setattr(pedido, "mp_init_point", "https://www.mercadopago.com.br/x"))
    usuario = _sem_telefone()
    _, token = _ir_ao_resumo(client_cliente)
    r = client_cliente.post("/checkout/confirmar", data={"token": token, "telefone": "(12) 99139-9090"})
    assert r.status_code == 303 and Pedido.query.count() == 1
    assert usuario.telefone == "12991399090"

