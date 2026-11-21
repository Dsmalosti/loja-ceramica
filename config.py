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
    # hospedagens em nuvem apagam arquivos enviados). Chaves do Cloudinary SÓ no .env do servidor.
    STORAGE_FOTOS = os.environ.get("STORAGE_FOTOS", "local")
    CLOUDINARY_CLOUD_NAME = os.environ.get("CLOUDINARY_CLOUD_NAME", "")
    CLOUDINARY_API_KEY = os.environ.get("CLOUDINARY_API_KEY", "")
    CLOUDINARY_API_SECRET = os.environ.get("CLOUDINARY_API_SECRET", "")
    CLOUDINARY_PASTA = os.environ.get("CLOUDINARY_PASTA", "julia-malosti/produtos")
    CLOUDINARY_API_URL = "https://api.cloudinary.com/v1_1"

    # Valores padrão = os da loja: se a variável faltar no servidor, o site
    # continua com o nome e o WhatsApp certos (o número não é segredo).
    # [back/duas-lojas] Antes o padrão era "Julia Malosti Arte Cerâmica": o site agora é do ateliê
    SITE_NAME = os.environ.get("SITE_NAME", "Malosti Arte Cerâmica")
    WHATSAPP_NUMBER = os.environ.get("WHATSAPP_NUMBER", "5512991399090")
    # Formulário de inscrição nos cursos (link público do Google Forms). O .env pode trocar;
    # vazio ou "#" (valor antigo do .env.example) usa o formulário da Julia.
    COURSES_FORM_URL = (
        (os.environ.get("COURSES_FORM_URL", "").strip() or "#").lstrip("#")
        or "https://docs.google.com/forms/d/e/1FAIpQLSdSF0H547-R3u6gUpEDPoP2Nh7LRaInjWotaR74-NietKsWCw/viewform"
    )

    # Mercado Pago (Checkout Pro). Sem token, o checkout mostra "pagamento
    # indisponível" em vez de quebrar. Chaves SÓ no .env do servidor.
    MP_ACCESS_TOKEN = os.environ.get("MP_ACCESS_TOKEN", "")
    MP_WEBHOOK_SECRET = os.environ.get("MP_WEBHOOK_SECRET", "")
    MP_API_URL = "https://api.mercadopago.com"
    # Endereço público do site (https, sem barra no fim): o Mercado Pago não aceita
    # localhost nas URLs de retorno e de notificação.
    SITE_URL = os.environ.get("SITE_URL", "").rstrip("/")
    # [back/compra-por-loja] FRETE_FIXO_CENTAVOS saiu: pedido é retirado no ateliê até definir a transportadora (#30)

    # E-mail transacional (Brevo). Sem chave, o site funciona normal e só não envia e-mails.
    # Chave SÓ no .env do servidor. O remetente precisa estar verificado no Brevo.
    BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
    EMAIL_REMETENTE = os.environ.get("EMAIL_REMETENTE", "")
    EMAIL_REMETENTE_NOME = os.environ.get("EMAIL_REMETENTE_NOME", "")
    # Quem recebe o aviso de "novo pedido pago" (a Julia). Vazio = não avisa.
    EMAIL_AVISO_PEDIDOS = os.environ.get("EMAIL_AVISO_PEDIDOS", "")
    APP_ENV = os.environ.get("APP_ENV", "development")


class DevelopmentConfig(Config):
    SECRET_KEY = os.environ.get("SECRET_KEY") or "chave-so-para-desenvolvimento"


class ProductionConfig(Config):
    # Exige SECRET_KEY de verdade (o create_app recusa subir sem ela)
    SESSION_COOKIE_SECURE = True
    # O Postgres fecha conexões paradas (comum em hospedagem que "dorme" entre acessos):
    # pre_ping testa a conexão antes de usar; recycle troca as que ficaram velhas.
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 280}
    # [back/seguranca-auditoria] Antes: sem valor (o navegador conferia CSS, JS e fotos a cada visita).
    # Agora 1 ano: o ?v= que app/estaticos.py põe no endereço troca quando o arquivo muda.
    SEND_FILE_MAX_AGE_DEFAULT = 365 * 24 * 3600


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
    # Brevo falso: nos testes o envio é simulado (email._requisicao)
    BREVO_API_KEY = "chave-brevo-falsa"
    EMAIL_REMETENTE = "loja@exemplo.test"
    EMAIL_AVISO_PEDIDOS = "julia@exemplo.test"


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
