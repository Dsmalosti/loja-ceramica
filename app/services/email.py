"""E-mails transacionais pela API do Brevo (https://developers.brevo.com).

Só biblioteca padrão (urllib), como o Mercado Pago. Regra de ouro: e-mail NUNCA derruba
a compra nem o cadastro: `enviar` não lança erro, devolve True/False e registra no log.
A chave (BREVO_API_KEY) fica só no .env do servidor.
"""
import json
import logging
import urllib.error
import urllib.request

from flask import current_app

log = logging.getLogger(__name__)

BREVO_URL = "https://api.brevo.com/v3/smtp/email"


def configurado():
    c = current_app.config
    return bool(c.get("BREVO_API_KEY") and c.get("EMAIL_REMETENTE"))


def _requisicao(corpo, chave):
    """Faz o POST no Brevo. Separada para os testes substituírem (nada sai pra internet)."""
    req = urllib.request.Request(
        BREVO_URL,
        data=json.dumps(corpo).encode("utf-8"),
        headers={"api-key": chave, "accept": "application/json", "content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resposta:
        return resposta.status


def enviar(para, assunto, texto, html=None, nome_para=None):
    """Envia um e-mail. Devolve True se o Brevo aceitou; False (sem lançar erro) se não."""
    if not para:
        return False
    if not configurado():
        # Em desenvolvimento mostra o conteúdo no terminal (dá pra copiar o link de recuperação).
        if not current_app.config.get("TESTING") and current_app.config.get("APP_ENV") != "production":
            log.warning("E-mail NÃO enviado (Brevo sem configurar). Para: %s | %s\n%s", para, assunto, texto)
        else:
            log.warning("E-mail não enviado: Brevo sem configurar (%s)", assunto)
        return False

    destino = {"email": para}
    if nome_para:
        destino["name"] = nome_para
    corpo = {
        "sender": {"email": current_app.config["EMAIL_REMETENTE"],
                   "name": current_app.config.get("EMAIL_REMETENTE_NOME") or current_app.config["SITE_NAME"]},
        "to": [destino],
        "subject": assunto,
        "textContent": texto,
    }
    if html:
        corpo["htmlContent"] = html
    try:
        _requisicao(corpo, current_app.config["BREVO_API_KEY"])
        return True
    except urllib.error.HTTPError as erro:
        log.error("Brevo recusou o e-mail '%s' (HTTP %s)", assunto, erro.code)
    except Exception as erro:  # rede fora, timeout etc.
        log.error("Falha ao enviar e-mail '%s': %s", assunto, type(erro).__name__)
    return False
