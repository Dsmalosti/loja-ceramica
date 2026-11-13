# Loja de Cerâmica

Site com loja, cursos presenciais, serviços e painel administrativo. Flask + SQLAlchemy + templates Jinja.

## Rodando pela primeira vez

```bash
python -m venv venv
venv\Scripts\activate            # Windows (no Linux/Mac: source venv/bin/activate)
pip install -r requirements-dev.txt
copy .env.example .env           # Windows (no Linux/Mac: cp .env.example .env)
```

### Banco de dados: escolha um

**A) SQLite local (mais simples, bom para o front).** Abra o `.env` e deixe a linha `DATABASE_URL=` vazia. Depois:

```bash
flask init-db
flask seed                       # produtos, cursos e serviços de exemplo
flask run
```

**B) Postgres com Docker (backend).**

```bash
docker compose up -d
flask db init                    # só na primeira vez, cria a pasta migrations/
flask db migrate -m "modelos iniciais"
flask db upgrade
flask seed
flask run
```

Se o Docker der problema, instale o Postgres normal, crie o banco `loja_ceramica` e ajuste a `DATABASE_URL` no `.env`.

> O `init-db` é só um atalho para o SQLite local descartável. No Postgres use sempre as migrations (`flask db migrate` e `flask db upgrade`).

### Criar o administrador

```bash
flask create-admin
```

Depois entre em `/entrar` e acesse `/admin/` (produtos com fotos, categorias, cursos e serviços).

Fotos de produtos são salvas em `app/static/uploads/` (ou na pasta indicada por `UPLOAD_DIR` no `.env`). Em hospedagens que apagam arquivos a cada deploy, troque o armazenamento em `app/services/imagens.py` (Cloudinary/S3) antes de publicar.

## Testes

```bash
pytest
```

## Como trabalhamos

- Uma branch por feature e Pull Request para a `main`.
- Backend mexe em `.py`, `migrations/` e `config.py`. Front mexe só em `app/templates/` e `app/static/`.
- O contrato de variáveis de cada página está em [`docs/TEMPLATES.md`](docs/TEMPLATES.md).
- Nunca versionar o `.env` (já está no `.gitignore`).

## Próximas etapas

Painel admin (CRUD) → carrinho e pedidos → pagamento (Mercado Pago, Checkout Pro) → testes, deploy e entrega.
