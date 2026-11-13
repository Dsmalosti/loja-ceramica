import os

from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, ".env"), override=True)


def _database_url():
    url = os.environ.get("DATABASE_URL")
    if not url:
        # Sem DATABASE_URL: usa SQLite local (bom para quem só mexe no front).
        return "sqlite:///" + os.path.join(basedir, "dev.db")
    # Alguns hosts entregam "postgres://", que o SQLAlchemy não aceita mais.
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    # Fixa o driver (psycopg 3), sem depender do padrão da versão instalada.
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # Fotos enviadas pelo painel. Fica dentro de static/ para o Flask servir.
    # Em produção, hosts como Render apagam esta pasta a cada deploy: antes de
    # ir ao ar, trocar o armazenamento (ver app/services/imagens.py).
    UPLOAD_DIR = os.environ.get("UPLOAD_DIR") or os.path.join(basedir, "app", "static", "uploads")
    # Limite do envio inteiro (várias fotos de até 5 MB cada)
    MAX_CONTENT_LENGTH = 25 * 1024 * 1024

    SITE_NAME = os.environ.get("SITE_NAME", "Loja de Cerâmica")
    WHATSAPP_NUMBER = os.environ.get("WHATSAPP_NUMBER", "5512999999999")
    COURSES_FORM_URL = os.environ.get("COURSES_FORM_URL", "#")


class DevelopmentConfig(Config):
    SECRET_KEY = os.environ.get("SECRET_KEY") or "chave-so-para-desenvolvimento"


class ProductionConfig(Config):
    # Exige SECRET_KEY de verdade (o create_app recusa subir sem ela)
    SESSION_COOKIE_SECURE = True


class TestingConfig(Config):
    TESTING = True
    SECRET_KEY = "chave-de-teste"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
