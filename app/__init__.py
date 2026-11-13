import os

from flask import Flask, render_template

from config import config_by_name

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
