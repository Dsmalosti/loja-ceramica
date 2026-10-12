from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db, login_manager


def agora():
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    criado_em = db.Column(db.DateTime(timezone=True), nullable=False, default=agora)

    def set_password(self, senha):
        self.password_hash = generate_password_hash(senha)

    def check_password(self, senha):
        return check_password_hash(self.password_hash, senha)

    @property
    def is_active(self):
        # O Flask-Login recusa o login de quem retornar False aqui
        return self.ativo


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False, index=True)
    ativa = db.Column(db.Boolean, nullable=False, default=True)

    produtos = db.relationship("Product", back_populates="categoria")


class Product(db.Model):
    __tablename__ = "products"
    __table_args__ = (
        db.CheckConstraint("preco_centavos >= 0", name="ck_products_preco_positivo"),
        db.CheckConstraint("estoque >= 0", name="ck_products_estoque_positivo"),
    )

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    slug = db.Column(db.String(180), unique=True, nullable=False, index=True)
    descricao = db.Column(db.Text, nullable=False, default="")
    # Preço em centavos (inteiro) evita erro de arredondamento com decimais
    preco_centavos = db.Column(db.Integer, nullable=False)
    estoque = db.Column(db.Integer, nullable=False, default=0)
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    criado_em = db.Column(db.DateTime(timezone=True), nullable=False, default=agora)
    categoria_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)

    categoria = db.relationship("Category", back_populates="produtos")
    imagens = db.relationship(
        "ProductImage",
        back_populates="produto",
        order_by="ProductImage.ordem",
        cascade="all, delete-orphan",
    )

    @property
    def disponivel(self):
        return self.ativo and self.estoque > 0

    @property
    def imagem_principal(self):
        return self.imagens[0] if self.imagens else None


class ProductImage(db.Model):
    __tablename__ = "product_images"

    id = db.Column(db.Integer, primary_key=True)
    produto_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    # Caminho dentro de static/ (ex.: 'uploads/caneca.jpg') ou URL completa
    caminho = db.Column(db.String(500), nullable=False)
    alt = db.Column(db.String(200), nullable=False, default="")
    ordem = db.Column(db.Integer, nullable=False, default=0)

    produto = db.relationship("Product", back_populates="imagens")


class Course(db.Model):
    """Curso presencial. A inscrição é feita num formulário externo (Google Forms)."""

    __tablename__ = "courses"

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(150), nullable=False)
    slug = db.Column(db.String(180), unique=True, nullable=False, index=True)
    descricao = db.Column(db.Text, nullable=False, default="")
    # Opcional: curso pode estar "sob consulta"
    valor_centavos = db.Column(db.Integer, nullable=True)
    duracao = db.Column(db.String(80), nullable=False, default="")
    ativo = db.Column(db.Boolean, nullable=False, default=True)


class Service(db.Model):
    __tablename__ = "services"

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(150), nullable=False)
    descricao = db.Column(db.Text, nullable=False, default="")
    ativo = db.Column(db.Boolean, nullable=False, default=True)


@login_manager.user_loader
def carregar_usuario(user_id):
    return db.session.get(User, int(user_id))
