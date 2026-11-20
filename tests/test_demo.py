"""Demo pra aprovação da Julia: seed com dados fictícios, admin de demo pelo ambiente."""
from pathlib import Path

import pytest

from app.models import Category, Course, Pedido, Product, Promocao, Service, User
from app.services.precos import preco_produto

RAIZ = Path(__file__).resolve().parent.parent
SENHA_DEMO = "senha-de-demo-bem-longa-123"


def rodar(app, *args):
    return app.test_cli_runner().invoke(args=["seed-demo", *args])


def test_seed_demo_cria_catalogo_completo(app):
    r = rodar(app)
    assert r.exit_code == 0, r.output
    assert Category.query.count() == 6 and Product.query.count() >= 10
    assert Course.query.count() == 3 and Service.query.count() == 2
    assert all(p.imagens for p in Product.query.all())  # toda peça tem foto
    assert Product.query.filter_by(estoque=0).count() >= 1  # mostra o selo "Indisponível"


def test_fotos_da_demo_existem_no_static(app):
    rodar(app)
    for produto in Product.query.all():
        for imagem in produto.imagens:
            assert imagem.caminho.startswith("img/inicio/") and imagem.caminho.endswith(".webp")
            assert (RAIZ / "app" / "static" / imagem.caminho).is_file(), imagem.caminho


def test_promocoes_da_demo(app):
    rodar(app)
    situacoes = sorted(p.situacao() for p in Promocao.query.all())
    assert "valendo" in situacoes and "agendada" in situacoes
    assert any(preco_produto(p).tem_desconto for p in Product.query.all())


def test_pedidos_da_demo_em_varias_situacoes_com_historico(app):
    rodar(app)
    status = {p.status for p in Pedido.query.all()}
    assert {"aguardando_pagamento", "pago", "entregue", "cancelado"} <= status
    assert all(p.historico for p in Pedido.query.all())
    assert all(p.pago_em for p in Pedido.query.filter(Pedido.status.in_(("pago", "entregue"))))


def test_seed_demo_pode_rodar_de_novo_sem_duplicar(app):
    rodar(app)
    contagem = (Product.query.count(), Pedido.query.count(), Promocao.query.count(), User.query.count())
    assert rodar(app).exit_code == 0
    assert (Product.query.count(), Pedido.query.count(), Promocao.query.count(), User.query.count()) == contagem


def test_em_producao_so_roda_com_permissao(app, monkeypatch):
    app.config["APP_ENV"] = "production"
    monkeypatch.delenv("PERMITIR_SEED_DEMO", raising=False)
    r = rodar(app)
    assert "PERMITIR_SEED_DEMO" in r.output and Product.query.count() == 0
    monkeypatch.setenv("PERMITIR_SEED_DEMO", "1")
    assert rodar(app).exit_code == 0 and Product.query.count() >= 10


# ---------- Admin de demo (senha só no ambiente) ----------

def test_admin_de_demo_vem_do_ambiente_e_a_senha_nao_aparece(app, monkeypatch):
    monkeypatch.setenv("DEMO_ADMIN_EMAIL", "Admin.Demo@Exemplo.com")
    monkeypatch.setenv("DEMO_ADMIN_SENHA", SENHA_DEMO)
    r = rodar(app)
    admin = User.query.filter_by(email="admin.demo@exemplo.com").one()
    assert admin.is_admin and admin.check_password(SENHA_DEMO)
    assert SENHA_DEMO not in r.output and SENHA_DEMO not in admin.password_hash


def test_sem_variaveis_nao_cria_admin(app, monkeypatch):
    monkeypatch.delenv("DEMO_ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("DEMO_ADMIN_SENHA", raising=False)
    rodar(app)
    assert User.query.filter_by(is_admin=True).count() == 0


def test_senha_curta_recusa_o_admin(app, monkeypatch):
    monkeypatch.setenv("DEMO_ADMIN_EMAIL", "admin.demo@exemplo.com")
    monkeypatch.setenv("DEMO_ADMIN_SENHA", "curta")
    r = rodar(app)
    assert User.query.filter_by(is_admin=True).count() == 0 and "12" in r.output


def test_rodar_de_novo_nao_troca_a_senha_do_admin(app, monkeypatch):
    monkeypatch.setenv("DEMO_ADMIN_EMAIL", "admin.demo@exemplo.com")
    monkeypatch.setenv("DEMO_ADMIN_SENHA", SENHA_DEMO)
    rodar(app)
    monkeypatch.setenv("DEMO_ADMIN_SENHA", "outra-senha-diferente-456")
    rodar(app)
    assert User.query.filter_by(email="admin.demo@exemplo.com").one().check_password(SENHA_DEMO)


# ---------- Servidor de demo (pagamento simulado) ----------

def test_servidor_de_demo_recusa_producao(monkeypatch):
    import runpy

    import config

    # Simula um servidor cujo .env diz production (o load_dotenv do config sobrescreveria o shell)
    monkeypatch.setattr(config, "load_dotenv", lambda *a, **k: None, raising=False)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setattr("sys.argv", ["servidor_demo.py"])
    modulo = runpy.run_path(str(RAIZ / "scripts" / "servidor_demo.py"), run_name="servidor_demo")
    with pytest.raises(SystemExit) as saida:
        modulo["main"]()
    assert "não roda em produção" in str(saida.value)
