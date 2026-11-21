import os

from flask import Flask, render_template
from werkzeug.middleware.proxy_fix import ProxyFix

from config import config_by_name

from . import estaticos, seguranca
from .blueprints import register_blueprints
from .cli import register_cli
from .extensions import csrf, db, login_manager, migrate
from .utils import register_template_helpers


def create_app(config_name=None):
    config_name = config_name or os.environ.get("APP_ENV", "development")

    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])
    app.config["APP_ENV"] = config_name

    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("Defina SECRET_KEY no .env antes de subir o app.")

    # [back/seguranca-auditoria] Novo. Em produção o site roda atrás do proxy do Render: sem isto,
    # todo pedido parecia vir do mesmo IP (o do proxy) e o limite de tentativas bloquearia todo mundo junto.
    if app.config.get("ATRAS_DE_PROXY"):
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    login_manager.login_view = "account.login"
    login_manager.login_message = "Faça login para continuar."
    login_manager.login_message_category = "erro"

    from . import models  # noqa: F401  (registra os modelos para as migrations)

    register_blueprints(app)
    register_template_helpers(app)
    register_cli(app)
    # [back/seguranca-auditoria] Novos: cabeçalhos de segurança e versão nos endereços de static/
    seguranca.registrar(app)
    estaticos.registrar(app)

    @app.errorhandler(403)
    def proibido(erro):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def nao_encontrado(erro):
        return render_template("errors/404.html"), 404

    @app.errorhandler(413)
    def arquivo_grande(erro):
        return render_template("errors/413.html"), 413

    return app
