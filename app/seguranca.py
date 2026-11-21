"""Cabeçalhos de segurança em toda resposta.

[back/seguranca-auditoria] Novo. Antes o site não mandava nenhum destes cabeçalhos (auditoria de 20/11/2026).

- Content-Security-Policy (CSP): lista de onde a página pode carregar script, estilo, foto e fonte.
  Se alguém conseguir injetar um <script> no HTML, o navegador se recusa a rodar. Por isso o site
  não tem script nem estilo escrito dentro do HTML: tudo fica em static/.
- X-Frame-Options e frame-ancestors: nenhum outro site pode abrir o nosso dentro de um quadro
  (o golpe de esconder o botão "Pagar" atrás de outra coisa).
- X-Content-Type-Options: o navegador não "adivinha" o tipo de um arquivo enviado.
- Referrer-Policy: outros sites só ficam sabendo de que domínio a pessoa veio, não da página.
- Strict-Transport-Security (HSTS): só em produção. Depois da primeira visita, o navegador só usa https.
"""

# Quem pode entregar o quê. Ao trocar de serviço (ex.: outro lugar para as fotos), atualize aqui.
FONTES_PERMITIDAS = {
    "default-src": ["'self'"],
    "script-src": ["'self'"],
    "style-src": ["'self'", "https://fonts.googleapis.com"],
    "font-src": ["'self'", "https://fonts.gstatic.com"],
    "img-src": ["'self'", "data:", "https://res.cloudinary.com"],
    # site.js consulta o CEP direto no ViaCEP
    "connect-src": ["'self'", "https://viacep.com.br"],
    # O checkout envia o formulário para nós e o servidor redireciona para o Mercado Pago:
    # o navegador também confere o destino do redirecionamento.
    "form-action": ["'self'", "https://*.mercadopago.com.br", "https://*.mercadopago.com"],
    "frame-ancestors": ["'none'"],
    "base-uri": ["'self'"],
    "object-src": ["'none'"],
}

HSTS_SEGUNDOS = 180 * 24 * 3600  # 6 meses


def politica_de_conteudo(producao=False):
    partes = [f"{diretiva} {' '.join(origens)}" for diretiva, origens in FONTES_PERMITIDAS.items()]
    if producao:
        partes.append("upgrade-insecure-requests")
    return "; ".join(partes)


def registrar(app):
    producao = app.config.get("APP_ENV") == "production"
    csp = politica_de_conteudo(producao)

    @app.after_request
    def cabecalhos_de_seguranca(resposta):
        h = resposta.headers
        h.setdefault("Content-Security-Policy", csp)
        h.setdefault("X-Frame-Options", "DENY")
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        h.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
        if producao:
            h.setdefault("Strict-Transport-Security", f"max-age={HSTS_SEGUNDOS}")
        return resposta
