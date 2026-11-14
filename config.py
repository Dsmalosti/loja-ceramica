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

    # Onde guardar as fotos: "local" (disco, bom pra dev) ou "cloudinary" (produção:
    # a Vercel apaga arquivos enviados). Chaves do Cloudinary SÓ no .env / Vercel.
    STORAGE_FOTOS = os.environ.get("STORAGE_FOTOS", "local")
    CLOUDINARY_CLOUD_NAME = os.environ.get("CLOUDINARY_CLOUD_NAME", "")
    CLOUDINARY_API_KEY = os.environ.get("CLOUDINARY_API_KEY", "")
    CLOUDINARY_API_SECRET = os.environ.get("CLOUDINARY_API_SECRET", "")
    CLOUDINARY_PASTA = os.environ.get("CLOUDINARY_PASTA", "julia-malosti/produtos")
    CLOUDINARY_API_URL = "https://api.cloudinary.com/v1_1"

    SITE_NAME = os.environ.get("SITE_NAME", "Loja de Cerâmica")
    WHATSAPP_NUMBER = os.environ.get("WHATSAPP_NUMBER", "5512999999999")
    COURSES_FORM_URL = os.environ.get("COURSES_FORM_URL", "#")

    # Mercado Pago (Checkout Pro). Sem token, o checkout mostra "pagamento
    # indisponível" em vez de quebrar. Chaves SÓ no .env / painel da Vercel.
    MP_ACCESS_TOKEN = os.environ.get("MP_ACCESS_TOKEN", "")
    MP_WEBHOOK_SECRET = os.environ.get("MP_WEBHOOK_SECRET", "")
    MP_API_URL = "https://api.mercadopago.com"
    # Endereço público do site (https, sem barra no fim): o Mercado Pago não aceita
    # localhost nas URLs de retorno e de notificação.
    SITE_URL = os.environ.get("SITE_URL", "").rstrip("/")
    # Frete fixo para entrega (a outra opção é retirar no ateliê, grátis)
    FRETE_FIXO_CENTAVOS = int(os.environ.get("FRETE_FIXO_CENTAVOS") or 2500)


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
    # Valores falsos: nos testes o Mercado Pago é simulado e nada sai pra internet
    STORAGE_FOTOS = "local"  # testes que usam o Cloudinary ligam e simulam
    CLOUDINARY_CLOUD_NAME = CLOUDINARY_API_KEY = CLOUDINARY_API_SECRET = ""
    MP_ACCESS_TOKEN = "TEST-token-falso"
    MP_WEBHOOK_SECRET = "segredo-de-teste"
    SITE_URL = "https://loja.exemplo.test"
    FRETE_FIXO_CENTAVOS = 2500


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
