"""Funções de apoio usadas nas rotas e nos templates."""
import re
import unicodedata
from urllib.parse import quote, urlparse

from flask import current_app, url_for


def slugify(texto):
    """'Caneca Azul Grande' -> 'caneca-azul-grande'."""
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-zA-Z0-9]+", "-", texto).strip("-").lower()


def brl(centavos):
    """Converte centavos em texto: 123456 -> 'R$ 1.234,56'."""
    if centavos is None:
        return ""
    centavos = int(centavos)
    sinal = "-" if centavos < 0 else ""
    reais, cent = divmod(abs(centavos), 100)
    return f"{sinal}R$ {reais:,}".replace(",", ".") + f",{cent:02d}"


def whatsapp_link(texto=""):
    """Link do WhatsApp da loja, com mensagem pré-preenchida (opcional)."""
    numero = current_app.config["WHATSAPP_NUMBER"]
    link = f"https://wa.me/{numero}"
    if texto:
        link += f"?text={quote(texto)}"
    return link


def image_url(caminho):
    """Aceita caminho dentro de static/ (ex.: 'uploads/a.jpg') ou URL completa."""
    if not caminho:
        return ""
    if caminho.startswith(("http://", "https://")):
        return caminho
    return url_for("static", filename=caminho)


def destino_seguro(destino):
    """Só aceita redirecionar para caminhos internos (evita open redirect)."""
    if not destino or "\\" in destino:
        return False
    partes = urlparse(destino)
    return (
        not partes.scheme
        and not partes.netloc
        and destino.startswith("/")
        and not destino.startswith("//")
    )


def register_template_helpers(app):
    app.add_template_filter(brl, "brl")
    app.add_template_global(whatsapp_link, "whatsapp_link")
    app.add_template_global(image_url, "image_url")

    @app.context_processor
    def injetar_site():
        return {"site_name": app.config["SITE_NAME"]}
