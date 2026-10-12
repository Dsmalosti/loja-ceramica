"""Comandos extras: flask init-db, flask create-admin, flask seed."""
import click

from .extensions import db
from .models import Category, Course, Product, Service, User
from .utils import slugify

PRODUTOS_EXEMPLO = {
    "Canecas": [
        ("Caneca esmaltada azul", "Caneca feita à mão com esmalte azul.", 5500, 8),
        ("Caneca rústica", "Caneca de barro com acabamento fosco.", 4800, 0),
    ],
    "Pratos": [
        ("Prato raso artesanal", "Prato raso torneado e esmaltado.", 7200, 5),
        ("Prato fundo", "Prato fundo, bom para sopas e massas.", 6800, 6),
    ],
    "Vasos": [
        ("Vaso de mesa", "Vaso pequeno para flores ou ramos secos.", 12000, 3),
    ],
}

CURSOS_EXEMPLO = [
    ("Introdução ao torno", "Primeiros passos no torno de cerâmica.", 25000, "4 encontros"),
    ("Modelagem manual", "Peças feitas à mão, sem torno.", None, "2 encontros"),
]

SERVICOS_EXEMPLO = [
    ("Peças sob encomenda", "Conjuntos e peças personalizadas, combinados pelo WhatsApp."),
    ("Queima de peças", "Queima de peças feitas em ateliê próprio."),
]


def register_cli(app):
    @app.cli.command("init-db")
    def init_db():
        """Cria as tabelas direto (atalho para desenvolvimento local com SQLite).

        Para o Postgres do backend, use as migrations: flask db upgrade.
        """
        db.create_all()
        click.echo("Tabelas criadas.")

    @app.cli.command("create-admin")
    @click.option("--nome", prompt=True)
    @click.option("--email", prompt=True)
    @click.password_option()
    def create_admin(nome, email, password):
        """Cria um usuário administrador."""
        email = email.strip().lower()
        if User.query.filter_by(email=email).first():
            click.echo("Já existe um usuário com esse e-mail.")
            return
        usuario = User(nome=nome.strip(), email=email, is_admin=True)
        usuario.set_password(password)
        db.session.add(usuario)
        db.session.commit()
        click.echo(f"Administrador {email} criado.")

    @app.cli.command("seed")
    def seed():
        """Cadastra dados de exemplo (só em desenvolvimento)."""
        if app.config["APP_ENV"] == "production":
            click.echo("Bloqueado em produção.")
            return
        if Category.query.first():
            click.echo("Já existem categorias; nada foi feito.")
            return
        for nome_categoria, produtos in PRODUTOS_EXEMPLO.items():
            categoria = Category(nome=nome_categoria, slug=slugify(nome_categoria))
            db.session.add(categoria)
            for nome, descricao, preco, estoque in produtos:
                db.session.add(
                    Product(
                        nome=nome,
                        slug=slugify(nome),
                        descricao=descricao,
                        preco_centavos=preco,
                        estoque=estoque,
                        categoria=categoria,
                    )
                )
        for titulo, descricao, valor, duracao in CURSOS_EXEMPLO:
            db.session.add(
                Course(
                    titulo=titulo,
                    slug=slugify(titulo),
                    descricao=descricao,
                    valor_centavos=valor,
                    duracao=duracao,
                )
            )
        for titulo, descricao in SERVICOS_EXEMPLO:
            db.session.add(Service(titulo=titulo, descricao=descricao))
        db.session.commit()
        click.echo("Dados de exemplo criados.")
