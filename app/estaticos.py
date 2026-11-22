"""Versão nos endereços de static/ para o navegador guardar CSS, JS e fotos por muito tempo.

[back/seguranca-auditoria] Novo. Antes o navegador perguntava ao servidor por cada arquivo a cada visita
(Cache-Control: no-cache). Agora todo url_for('static', ...) ganha ?v=<impressão do conteúdo>.
Em produção o arquivo pode ficar 1 ano no cache (SEND_FILE_MAX_AGE_DEFAULT no config): quando o
arquivo muda, a impressão muda, o endereço muda, e o navegador baixa a versão nova na hora.
"""
import hashlib
import os
from functools import lru_cache


@lru_cache(maxsize=1024)
def _impressao(caminho, modificado_em):
    # modificado_em entra na chave do cache: arquivo alterado (no PC) gera impressão nova
    with open(caminho, "rb") as arquivo:
        return hashlib.md5(arquivo.read(), usedforsecurity=False).hexdigest()[:10]


def registrar(app):
    pasta = os.path.realpath(app.static_folder)

    @app.url_defaults
    def versao_do_estatico(endpoint, valores):
        if endpoint != "static" or "v" in valores or not valores.get("filename"):
            return
        caminho = os.path.realpath(os.path.join(pasta, valores["filename"]))
        if not caminho.startswith(pasta + os.sep):
            return
        try:
            modificado_em = os.stat(caminho).st_mtime_ns
        except OSError:
            return  # arquivo que não existe: o endereço sai sem versão (e dá 404 como antes)
        valores["v"] = _impressao(caminho, modificado_em)
