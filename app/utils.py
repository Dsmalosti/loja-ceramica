"""Funções de apoio usadas nas rotas e nos templates."""
import re
import unicodedata
from datetime import timedelta, timezone
from urllib.parse import quote, urlparse

from flask import current_app, url_for
from markupsafe import Markup, escape


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


# Horário de Brasília. O Brasil não tem horário de verão desde 2019, então um
# deslocamento fixo basta (e evita depender do pacote tzdata no Windows).
FUSO_BRASILIA = timezone(timedelta(hours=-3))


def data_br(momento, com_hora=False):
    """datetime (UTC) -> '14/11/2026' ou '14/11/2026 às 13:05' no horário de Brasília."""
    if momento is None:
        return ""
    if momento.tzinfo is None:  # SQLite devolve sem fuso: foi gravado em UTC
        momento = momento.replace(tzinfo=timezone.utc)
    local = momento.astimezone(FUSO_BRASILIA)
    return local.strftime("%d/%m/%Y às %H:%M" if com_hora else "%d/%m/%Y")


def whatsapp_link(texto=""):
    """Link do WhatsApp da loja, com mensagem pré-preenchida (opcional)."""
    numero = current_app.config["WHATSAPP_NUMBER"]
    link = f"https://wa.me/{numero}"
    if texto:
        link += f"?text={quote(texto)}"
    return link


def whatsapp_cliente(telefone, texto=""):
    """Link do WhatsApp do CLIENTE (painel da Julia). '' se não houver telefone válido."""
    digitos = re.sub(r"\D", "", telefone or "")
    if len(digitos) not in (10, 11):
        return ""
    link = f"https://wa.me/55{digitos}"
    if texto:
        link += f"?text={quote(texto)}"
    return link


def telefone_br(telefone):
    """'12991112222' -> '(12) 99111-2222' (fixo: '(12) 3456-7890')."""
    d = re.sub(r"\D", "", telefone or "")
    if len(d) == 11:
        return f"({d[:2]}) {d[2:7]}-{d[7:]}"
    if len(d) == 10:
        return f"({d[:2]}) {d[2:6]}-{d[6:]}"
    return telefone or ""


CLOUDINARY_UPLOAD = re.compile(r"^(https://res\.cloudinary\.com/[\w-]+/image/upload/)(.+)$")


def image_url(caminho, largura=1200):
    """Aceita caminho dentro de static/ (ex.: 'uploads/a.jpg') ou URL completa.

    Foto do Cloudinary sai em WebP/AVIF (f_auto), qualidade automática (q_auto) e
    no máximo `largura` px (c_limit não aumenta foto pequena): bem mais leve no celular.
    """
    if not caminho:
        return ""
    nuvem = CLOUDINARY_UPLOAD.match(caminho)
    if nuvem:
        return f"{nuvem.group(1)}f_auto,q_auto,c_limit,w_{int(largura)}/{nuvem.group(2)}"
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


# [back/painel-julia] Texto que a Julia escreve no painel vira HTML SEGURO: primeiro escapa tudo
# (ninguém consegue colocar <script> nem HTML), depois aplica só estas marcas:
#   linha em branco = novo parágrafo · linha começando com "- " = item de lista
#   **assim** = negrito · *assim* = destaque (itálico na cor da marca)
# A marca só vale encostada no texto e fora de palavras: "2*3" continua sendo conta
_NEGRITO = re.compile(r"(?<![\w*])\*\*(?=\S)(.+?)(?<=\S)\*\*(?![\w*])")
_DESTAQUE = re.compile(r"(?<![\w*])\*(?=[^\s*])(.+?)(?<=[^\s*])\*(?![\w*])")
_ITEM = re.compile(r"^[-•]\s+(.*)")


def _marcas(texto):
    html = str(escape(texto))
    html = _NEGRITO.sub(r"<strong>\1</strong>", html)
    return _DESTAQUE.sub(r"<em>\1</em>", html)


def texto_destaque(texto):
    """Uma linha (título, slogan) com **negrito** e *destaque*."""
    return Markup(_marcas(texto or ""))


def sem_marcas(texto):
    """Tira os asteriscos (para <title>, descrição de busca e lugares sem formatação)."""
    return re.sub(r"\*+", "", texto or "")


def texto_formatado(texto):
    """Texto longo do painel em parágrafos e listas."""
    blocos, paragrafo, lista = [], [], []

    def fechar():
        if paragrafo:
            blocos.append("<p>" + "<br>".join(paragrafo) + "</p>")
            paragrafo.clear()
        if lista:
            blocos.append("<ul>" + "".join(f"<li>{item}</li>" for item in lista) + "</ul>")
            lista.clear()

    for linha in (texto or "").replace("\r\n", "\n").split("\n"):
        linha = linha.strip()
        item = _ITEM.match(linha)
        if not linha:
            fechar()
        elif item:
            if paragrafo:
                fechar()
            lista.append(_marcas(item.group(1)))
        else:
            if lista:
                fechar()
            paragrafo.append(_marcas(linha))
    fechar()
    return Markup("".join(blocos))


def register_template_helpers(app):
    app.add_template_filter(brl, "brl")
    app.add_template_filter(data_br, "data_br")

    # Preço com promoção (único lugar que calcula: app/services/precos.py)
    from .lojas import LOJAS
    from .services.precos import preco_curso, preco_produto

    app.add_template_global(preco_produto, "preco")
    app.add_template_global(preco_curso, "preco_curso")
    app.add_template_global(whatsapp_link, "whatsapp_link")
    app.add_template_global(whatsapp_cliente, "whatsapp_cliente")
    app.add_template_filter(telefone_br, "telefone")
    # [back/painel-julia] formatação dos textos do painel
    app.add_template_filter(texto_formatado, "texto_formatado")
    app.add_template_filter(texto_destaque, "texto_destaque")
    app.add_template_filter(sem_marcas, "sem_marcas")
    from .textos import texto_site
    app.add_template_global(texto_site, "texto_site")
    app.add_template_global(image_url, "image_url")
    app.add_template_global(LOJAS, "lojas")  # [back/duas-lojas] nomes das duas lojas nas telas

    @app.context_processor
    def injetar_site():
        return {"site_name": app.config["SITE_NAME"]}
