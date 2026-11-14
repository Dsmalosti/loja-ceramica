"""Build na Vercel (vercel.json -> "buildCommand": "python build.py").

1. Copia app/static para public/static: a Vercel serve public/** pela CDN, nas mesmas
   URLs /static/... que o url_for('static') gera (a doc da Vercel pede pra não depender
   do static_folder do Flask). Fotos enviadas (uploads/) ficam de fora: em produção vão pro Cloudinary.
2. Opcional, pelo ambiente do projeto na Vercel:
   MIGRAR_NO_BUILD=1     -> flask db upgrade (cria/atualiza as tabelas no Postgres)
   SEED_DEMO_NO_BUILD=1  -> flask seed-demo (dados fictícios; também exige PERMITIR_SEED_DEMO=1)
   Assim ninguém precisa rodar comando contra o banco de produção a partir do próprio computador.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent


def copiar_estaticos(raiz=RAIZ):
    destino = Path(raiz) / "public" / "static"
    shutil.rmtree(destino, ignore_errors=True)
    shutil.copytree(Path(raiz) / "app" / "static", destino, ignore=shutil.ignore_patterns("uploads"))
    return destino


def flask(*args):
    print("$ flask", *args, flush=True)
    subprocess.run([sys.executable, "-m", "flask", "--app", "wsgi", *args], cwd=RAIZ, check=True)


if __name__ == "__main__":
    print("Estáticos copiados para", copiar_estaticos(), flush=True)
    if os.environ.get("MIGRAR_NO_BUILD") == "1":
        flask("db", "upgrade")
    if os.environ.get("SEED_DEMO_NO_BUILD") == "1":
        flask("seed-demo")
