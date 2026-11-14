---
name: saas-flask-seguranca
description: Use antes de lançar ou revisar a loja Julia Malosti (Flask/SQLAlchemy) — isolamento entre clientes, admin, CSRF, rate limit, headers, segredos, uploads de fotos, checkout Mercado Pago e LGPD.
---

# Segurança da loja (Flask) — checklist de lançamento

Segurança é **pré-condição de lançamento**, não feature. Cada item tem o "porquê": se não entender o
porquê, não marque como feito. Para cada falha: severidade (P0 bloqueia lançamento) + correção + teste.

## 1. Isolamento entre clientes

- Pedido, endereço, wishlist: sempre filtrar pelo dono.
  ```python
  pedido = Pedido.query.filter_by(id=id, user_id=current_user.id).first_or_404()
  ```
  Nunca `Model.query.get(id)` vindo da URL em dado de cliente.
- Teste obrigatório: logado como cliente A, pedir `/conta/pedidos/<id do cliente B>` → **404** (não 403).

## 2. Admin

- Esconder link no template é cosmético. Toda rota `/admin/*` checa `is_admin` no servidor
  (o blueprint do Diogo já faz; manter assim em rota nova).
- Página de detalhe do produto exige login (regra de negócio da Julia) → `@login_required` na rota.

## 3. Autenticação

- Senha com hash forte (já é do projeto — não trocar).
- Rate limit em `/entrar` e "esqueci senha" (Flask-Limiter, ex. `5/minute`).
- Mesma mensagem pra "e-mail não existe" e "senha errada".
- Cookies: `SESSION_COOKIE_SECURE`, `HTTPONLY`, `SAMESITE='Lax'` em produção.
- Redirect pós-login só pra caminho interno (já testado: `evil.com` não passa).

## 4. Formulários

- CSRF em **todo** POST: `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">`.
  Sair (logout) é POST com CSRF, nunca link GET.
- Validação no servidor sempre (`app/validators.py`).
- Dinheiro em **centavos inteiros** no banco, exibido com o filtro `|brl`. Nada de float.
- Nunca `|safe` em dado vindo do usuário/admin.

## 5. Front sem script inline

- JS novo vai em `app/static/js/`. Nada de `onclick=` nem `<script>` inline → permite CSP `script-src 'self'`.
- Headers em produção: HSTS, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`,
  `frame-ancestors 'none'`.

## 6. Segredos

- `.env` no `.gitignore` e **nunca commitado** (`git log --all -- .env` tem que vir vazio). Se vazou, trocar a chave.
- Produção recusa subir sem `SECRET_KEY` (já é assim no `create_app`).
- Chaves do Mercado Pago só em variável de ambiente; chave de teste ≠ produção.

## 7. Uploads de fotos (painel)

- Tipo conferido pelos bytes (JPEG/PNG/WEBP), não pela extensão; tamanho máximo (`MAX_CONTENT_LENGTH` → página 413).
- Nome gerado no servidor. Já implementado em `app/services/imagens.py` — manter.
- Vercel tem disco efêmero: em produção as fotos vão pra storage externo (Cloudinary/S3/Vercel Blob).

## 8. Checkout e pagamento (Mercado Pago)

- **Nenhum dado de cartão passa pelo nosso servidor nem vai pro banco** (usar Checkout Pro / Bricks).
- Webhook valida assinatura e é **idempotente** (mesmo evento 2× não confirma 2×: unique no id do evento).
- Valor e status confirmados vêm do Mercado Pago, nunca do formulário.
- Estoque baixa só com pagamento aprovado.

## 9. LGPD

- Coletar só o necessário (nome, e-mail, endereço de entrega).
- Cliente pode pedir exclusão dos dados. Logs sem senha/token.

## Como usar

1. Rode por seção e marque com evidência (arquivo:linha ou teste).
2. Não aplique mudança de backend sem explicar ao Adauto e sem revisão do Diogo.
