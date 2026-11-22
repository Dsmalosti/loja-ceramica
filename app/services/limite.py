"""Limite de tentativas contra robôs: login, "esqueci a senha" e criação de conta.

[back/seguranca-auditoria] Novo. Antes não havia limite: um robô podia testar senhas sem parar
ou disparar milhares de e-mails de recuperação pela conta do Brevo.

Guarda cada tentativa no banco (tabela tentativas_acesso), e não na memória, porque o servidor roda
com 2 processos (gunicorn --workers 2) e reinicia a cada deploy: um contador em memória teria
um limite diferente em cada processo e zeraria toda vez. Sem dependência nova.
"""
from datetime import timedelta

from flask import request

from ..extensions import db
from ..models import TentativaAcesso, agora

# (quantas tentativas, em quanto tempo). Ajuste aqui se a Julia reclamar de bloqueio.
LOGIN_POR_EMAIL = (5, timedelta(minutes=15))   # senhas erradas na mesma conta
LOGIN_POR_IP = (20, timedelta(minutes=15))     # senhas erradas vindas do mesmo endereço
SENHA_POR_EMAIL = (3, timedelta(hours=1))      # pedidos de "esqueci a senha"
SENHA_POR_IP = (10, timedelta(hours=1))
CADASTRO_POR_IP = (10, timedelta(hours=1))     # contas criadas do mesmo endereço

GUARDAR_POR = timedelta(days=1)  # a política de privacidade promete apagar em 1 dia


def ip():
    """Endereço de quem fez o pedido. Em produção o ProxyFix (app/__init__.py) já leu o do proxy."""
    return request.remote_addr or "desconhecido"


def excedeu(chave, regra):
    maximo, janela = regra
    desde = agora() - janela
    feitas = TentativaAcesso.query.filter(TentativaAcesso.chave == chave,
                                          TentativaAcesso.criado_em >= desde).count()
    return feitas >= maximo


def anotar(*chaves):
    for chave in chaves:
        db.session.add(TentativaAcesso(chave=chave[:300]))
    # Limpeza de passagem: o que tem mais de 1 dia não serve para nada e não fica guardado
    TentativaAcesso.query.filter(TentativaAcesso.criado_em < agora() - GUARDAR_POR).delete(
        synchronize_session=False)
    db.session.commit()


def esquecer(chave):
    """Zera as tentativas de uma chave (ex.: a pessoa acertou a senha)."""
    TentativaAcesso.query.filter_by(chave=chave).delete(synchronize_session=False)
    db.session.commit()
