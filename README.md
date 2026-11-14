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

## Deploy na Vercel (demo)

A Vercel acha o Flask sozinha pelo `app` do `wsgi.py`. O `vercel.json` roda `python build.py`, que copia
`app/static` para `public/static` (servido pela CDN, mesmas URLs `/static/...`) e, se pedido no ambiente,
roda `flask db upgrade` e `flask seed-demo` no build.

1. Importar o repositório na Vercel (Add New > Project) e escolher a branch da demo.
2. **Storage > Neon (Postgres)**: criar e conectar ao projeto. O `DATABASE_URL` entra sozinho.
3. **Settings > Environment Variables > Import .env**: importar o `.env.vercel` (gerado localmente, fora do Git).
   Ele traz `SECRET_KEY`, `APP_ENV=production`, o admin de demo e as chaves `MIGRAR_NO_BUILD`,
   `SEED_DEMO_NO_BUILD` e `PERMITIR_SEED_DEMO`.
4. Fazer o deploy; depois preencher `SITE_URL` com o endereço e fazer redeploy.
5. **Lançamento real:** tirar `SEED_DEMO_NO_BUILD` e `PERMITIR_SEED_DEMO`, trocar o `SECRET_KEY`, usar uma conta
   **Pro** (o plano Hobby da Vercel é só para uso não comercial) e apagar os dados fictícios.

`flask seed-demo` cria peças com as fotos de `static/img/inicio`, cursos, promoções e pedidos **fictícios**;
pode rodar de novo sem duplicar. O admin de demo só nasce com `DEMO_ADMIN_EMAIL` e `DEMO_ADMIN_SENHA` no
ambiente, e a senha nunca é impressa.

## Fotos em produção (Cloudinary)

A Vercel apaga os arquivos enviados a cada deploy, então em produção as fotos vão para o Cloudinary
(plano grátis cobre a loja). No dev e nos testes continuam no disco (`STORAGE_FOTOS=local`).

1. Crie a conta em cloudinary.com e copie de **Settings > API Keys**: Cloud name, API Key e API Secret.
2. No `.env` / Vercel: `STORAGE_FOTOS=cloudinary`, `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`,
   `CLOUDINARY_API_SECRET` (e, se quiser, `CLOUDINARY_PASTA`). O secret nunca vai pro Git nem pro chat.
3. Pronto: o painel sobe por upload assinado e o site entrega cada foto em WebP/AVIF no tamanho da tela
   (`image_url(caminho, 600)` → `f_auto,q_auto,c_limit,w_600`). Fotos antigas em disco continuam funcionando.

## Pagamento (Mercado Pago, Checkout Pro)

O cliente paga com Pix ou cartão **na página do Mercado Pago**: dado de cartão nunca passa pelo nosso servidor.
O estoque só baixa quando o Mercado Pago confirma o pagamento (webhook em `/pagamento/webhook` ou volta do cliente).

1. Em mercadopago.com.br/developers > Suas integrações, crie a aplicação (Checkout Pro) e copie as
   **credenciais de teste** para o `.env`: `MP_ACCESS_TOKEN`.
2. Em Webhooks > Configurar notificações, use a URL `https://<seu-site>/pagamento/webhook`, evento
   **Pagamentos**, e copie a assinatura secreta para `MP_WEBHOOK_SECRET`.
3. `SITE_URL` = endereço público com https. O Mercado Pago **não aceita localhost**: o teste ponta a ponta no
   sandbox é feito no site publicado (preview da Vercel), com o usuário comprador de teste.
4. Sem `MP_ACCESS_TOKEN`/`SITE_URL`, o checkout mostra "Pagamento indisponível" (não quebra).

Nos testes (`tests/test_checkout.py`) o Mercado Pago é simulado: nada sai pra internet.

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
