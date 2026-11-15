# Julia Malosti Arte Cerâmica

Site com loja, cursos presenciais, serviços e painel administrativo. Flask + SQLAlchemy + templates Jinja.

## Rodando pela primeira vez

```bash
python -m venv venv
venv\Scripts\activate            # Windows (no Linux/Mac: source venv/bin/activate)
pip install -r requirements-dev.txt
copy .env.example .env           # Windows (no Linux/Mac: cp .env.example .env)
```

### Variáveis do `.env`

| Variável | Valor da loja | Para que serve |
|---|---|---|
| `APP_ENV` | `development` (local) / `production` (Vercel) | Escolhe a configuração em `config.py` |
| `SECRET_KEY` | gere com `python -c "import secrets; print(secrets.token_hex(32))"` | Assina a sessão e o login. Nunca versionar |
| `DATABASE_URL` | vazio = SQLite local | Banco de dados |
| `WHATSAPP_NUMBER` | `5512991399090` | Número usado em **todos** os links de WhatsApp (só dígitos: 55 + DDD + número) |
| `SITE_NAME` | `"Julia Malosti Arte Cerâmica"` | Nome nas abas do navegador, no rodapé e nos leitores de tela |
| `COURSES_FORM_URL` | `#` (sem formulário) | Link do Google Forms dos cursos. Com `#`, a inscrição vai pro WhatsApp |

Nos templates, link de WhatsApp é sempre `{{ whatsapp_link('mensagem') }}`, nunca `wa.me/...` escrito à mão:
assim, trocar o número no `.env` troca o site inteiro. Há um teste que barra link escrito à mão.

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
