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
| `APP_ENV` | `development` (local) / `production` (servidor) | Escolhe a configuração em `config.py` |
| `SECRET_KEY` | gere com `python -c "import secrets; print(secrets.token_hex(32))"` | Assina a sessão e o login. Nunca versionar |
| `DATABASE_URL` | vazio = SQLite local | Banco de dados |
| `WHATSAPP_NUMBER` | `5512991399090` | Número usado em **todos** os links de WhatsApp (só dígitos: 55 + DDD + número) |
| `SITE_NAME` | `"Julia Malosti Arte Cerâmica"` | Nome nas abas do navegador, no rodapé e nos leitores de tela |
| `COURSES_FORM_URL` | já vem o formulário da Julia | Link do Google Forms dos cursos (botão "Quero me inscrever"). Só preencha para trocar o formulário |
| `BREVO_API_KEY`, `EMAIL_REMETENTE`, `EMAIL_REMETENTE_NOME`, `EMAIL_AVISO_PEDIDOS` | ver seção E-mail | Envio de e-mails (opcional em dev) |

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

## Demo no computador (para a aprovação da Julia)

Banco novo, montado pelas migrações (testa a cadeia inteira), com dados **fictícios**:

```bash
flask db upgrade                 # SQLite local (DATABASE_URL vazio no .env)
flask seed-demo                  # 11 peças com fotos, cursos, promoções e pedidos fictícios
flask run
```

Para nascer um admin de demonstração, coloque no `.env` (nunca no Git nem no chat)
`DEMO_ADMIN_EMAIL=...` e `DEMO_ADMIN_SENHA=...` (mínimo 12 caracteres) antes do `seed-demo`.
Sem as do Cloudinary use `STORAGE_FOTOS=local`. O `seed-demo` pode rodar de novo sem duplicar.

**Testar a compra inteira sem as chaves do Mercado Pago** (e no celular, na mesma rede Wi-Fi):

```bash
python scripts/servidor_demo.py          # http://localhost:5000
python scripts/servidor_demo.py --rede   # mostra o endereço pra abrir no celular
```

O `servidor_demo.py` usa o código real e só simula a resposta do Mercado Pago (aprovado).
Não faz parte do site publicado e se recusa a rodar com `APP_ENV=production`.
Com `flask run` (sem o simulador) o checkout mostra "Pagamento indisponível" até ter as chaves.

## Fotos em produção (Cloudinary)

Hospedagens em nuvem costumam apagar os arquivos enviados a cada deploy, então em produção as fotos vão
para o Cloudinary (plano grátis cobre a loja). No dev e nos testes continuam no disco (`STORAGE_FOTOS=local`).

1. Crie a conta em cloudinary.com e copie de **Settings > API Keys**: Cloud name, API Key e API Secret.
2. No `.env` do servidor: `STORAGE_FOTOS=cloudinary`, `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`,
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
   sandbox é feito no site publicado, com o usuário comprador de teste. No computador, use o servidor de demo
   com o pagamento simulado (abaixo).
4. Sem `MP_ACCESS_TOKEN`/`SITE_URL`, o checkout mostra "Pagamento indisponível" (não quebra).

Nos testes (`tests/test_checkout.py`) o Mercado Pago é simulado: nada sai pra internet.

## E-mail (Brevo)

Recuperação de senha e avisos de pedido pago (um para a cliente, outro para a Julia) saem pela API do Brevo.
Sem a chave o site funciona igual, só não envia (em desenvolvimento o texto do e-mail aparece no terminal).

1. Em brevo.com crie a conta, vá em **Remetentes, domínios e IPs** e verifique o e-mail remetente
   (ideal: um e-mail do domínio da loja; autentique o domínio com SPF/DKIM para não cair no spam).
2. Em **SMTP e API > Chaves de API** gere uma chave (API v3).
3. No `.env` do servidor: `BREVO_API_KEY`, `EMAIL_REMETENTE`, `EMAIL_REMETENTE_NOME` e
   `EMAIL_AVISO_PEDIDOS` (e-mail da Julia). A chave nunca vai pro Git nem pro chat.

Cliente: `/entrar` > "Esqueci minha senha" envia um link que vale 1 hora e só funciona uma vez.
Nos testes (`tests/test_email.py`) o Brevo é simulado: nada sai pra internet.

## Publicar no Render (demonstração para a Julia)

O `render.yaml` cria o site e um Postgres grátis de uma vez (Blueprint). É para **demonstração**: o plano grátis dorme
após 15 min parado e o banco grátis expira em 30 dias. Para vender de verdade, use planos pagos (ver abaixo).

1. No GitHub, o código precisa estar na `main` (com o `render.yaml`).
2. Em render.com: **New > Blueprint**, escolha o repositório e aplique. O Render pergunta as variáveis marcadas
   como "sync: false": `DEMO_ADMIN_EMAIL` e `DEMO_ADMIN_SENHA` (login do admin de demonstração, senha com 12+
   caracteres) e `SITE_URL` (deixe em branco por enquanto).
3. Quando o deploy terminar, copie o endereço `https://....onrender.com`, volte em **Environment** do serviço, preencha
   `SITE_URL` com ele (sem barra no fim) e salve (o Render reinicia sozinho).
4. A cada início o serviço roda `flask db upgrade` e `flask seed-demo` (idempotente: não duplica). Entre em `/entrar`
   com o admin de demonstração e abra `/admin/`.
5. Pagamento: sem `MP_ACCESS_TOKEN` o checkout mostra "Pagamento indisponível". Para testar a compra no site publicado,
   use as credenciais de **teste** do Mercado Pago e a URL do webhook `https://<site>/pagamento/webhook`.

Antes de a loja valer de verdade: tirar `PERMITIR_SEED_DEMO`, trocar para banco e servidor pagos, `STORAGE_FOTOS=cloudinary`,
domínio da Julia (atualizar `SITE_URL` e o webhook) e `flask create-admin` para a conta real.

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
