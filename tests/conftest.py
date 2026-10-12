import pytest

from app import create_app
from app.extensions import db
from app.models import Category, Product, User


@pytest.fixture()
def app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def catalogo(app):
    """Uma categoria com um produto ativo e um produto desativado."""
    categoria = Category(nome="Canecas", slug="canecas")
    db.session.add(categoria)
    db.session.add_all(
        [
            Product(nome="Caneca azul", slug="caneca-azul", preco_centavos=5500,
                    estoque=3, categoria=categoria),
            Product(nome="Caneca oculta", slug="caneca-oculta", preco_centavos=1000,
                    estoque=1, ativo=False, categoria=categoria),
        ]
    )
    db.session.commit()


@pytest.fixture()
def criar_usuario(app):
    def _criar(email="cliente@exemplo.com", senha="senha-segura-123", admin=False):
        usuario = User(nome="Pessoa Teste", email=email, is_admin=admin)
        usuario.set_password(senha)
        db.session.add(usuario)
        db.session.commit()
        return usuario

    return _criar
