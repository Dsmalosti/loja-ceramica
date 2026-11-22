# back/seguranca-auditoria

Correções de backend da auditoria de 20/11/2026 (`docs/auditoria/2026-11-20.md`), aprovadas pelo Adauto.
**Branch empilhada:** sai de `front/auditoria` (PR #40). Cada item é um commit, para revisar um por vez.

## O que mudou, por quê e como era antes

| Commit | O que mudou | Por quê | Como era |
|---|---|---|---|
| 1 | `/privacidade`, `/termos`, `/robots.txt`, `/sitemap.xml` em `public.py`; links no rodapé, no cadastro e no checkout | P0 da LGPD: o site coleta nome, e-mail, telefone e endereço | As quatro davam 404 |
| 2 | `app/seguranca.py` (CSP, X-Frame-Options, nosniff, Referrer-Policy, Permissions-Policy, HSTS só em produção) e `app/estaticos.py` (`?v=` em todo `url_for('static')`); `SEND_FILE_MAX_AGE_DEFAULT` de 1 ano em produção | P1: nenhum cabeçalho de segurança no site publicado. P2: CSS e JS com `no-cache` | Sem cabeçalhos; arquivos conferidos a cada visita |
| 3 | Tabela `tentativas_acesso` (migração `f2b7c9d4e810`) e `app/services/limite.py`; limite em `/entrar`, `/esqueci-senha` e `/cadastro`; `session.clear()` antes de `login_user`; `ProxyFix` em produção (`ATRAS_DE_PROXY`) | P1: dava para testar senhas sem parar e disparar e-mails em massa pelo Brevo | Sem limite; a sessão de antes do login continuava |
| 4 | Campo de WhatsApp obrigatório no checkout, salvo na conta | P1: o resumo promete aviso pelo WhatsApp, mas o telefone era opcional e nunca pedido | O checkout não pedia telefone |

## Os limites (em `app/services/limite.py`)
| Ação | Limite |
|---|---|
| Senha errada na mesma conta | 5 em 15 minutos |
| Senha errada no mesmo IP (qualquer conta) | 20 em 15 minutos |
| "Esqueci a senha" | 3 por e-mail ou 10 por IP por hora. Passou do limite, não envia, e a resposta é a mesma |
| Criar conta | 10 por IP por hora |

As tentativas ficam no banco, não na memória, porque o Render roda 2 processos do gunicorn e reinicia a cada deploy. Registros com mais de 1 dia são apagados de passagem, como a política de privacidade promete.

## CSP: o que está liberado
- **Script:** só arquivos do próprio site. Não há script em linha; o JSON-LD é dado e não roda.
- **Estilo e fonte:** o próprio site e o Google Fonts.
- **Foto:** o próprio site, `data:` (favicon) e o Cloudinary.
- **Conexão:** o próprio site e o ViaCEP (busca do CEP, PR #37).
- **Envio de formulário:** o próprio site e o Mercado Pago, porque o checkout redireciona para lá e o navegador confere o destino.
- **Ao trocar um serviço** (outro lugar para as fotos, um mapa embutido), atualize `FONTES_PERMITIDAS` em `app/seguranca.py`. Se esquecer, o navegador bloqueia e avisa no console.

## Como foi testado
- **`tests/test_seguranca_auditoria.py`:** 28 testes novos. Suíte inteira com **528 passando** (eram 500).
- **Migração no SQLite:** upgrade, downgrade e upgrade, sem diferença entre o modelo e o banco.
- **Playwright em 390 e 1440:**
  - Todas as páginas públicas e as 9 telas do painel, sem nenhum bloqueio da CSP.
  - Checkout barra o WhatsApp vazio, e o redirecionamento para o Mercado Pago passa pela CSP (simulado, nada foi enviado ao Mercado Pago).
  - O login trava na 6ª tentativa.
- **Regressão:** QA da reformulação em 360, 390, 768 e 1440 e QA da auditoria, sem falhas.

## Como revisar
`git diff origin/front/auditoria..origin/back/seguranca-auditoria`, ou commit por commit.

## Riscos e o que conferir no deploy
- **Migração nova:** o `startCommand` do Render já roda `flask db upgrade`. No Postgres só conferi o SQL. A primeira subida confirma.
- **IP atrás do proxy:** `ProxyFix(x_for=1)` confia no último endereço do `X-Forwarded-For`. Se o Render entregar ali o IP da Cloudflare em vez do cliente [Provável que não], o limite por IP valeria para um grupo grande de pessoas. O limite por conta continua valendo do mesmo jeito.
  - **Como conferir:** depois do deploy, errar a senha 20 vezes de um celular no 4G e ver se o computador, em outra rede, continua entrando.
- **HSTS:** vale para o endereço `onrender.com` desde já. Com o domínio próprio, ele passa a valer lá também.
- **Texto das páginas legais:** rascunho para a Julia revisar. Faltam razão social e CNPJ, que não estão no projeto.
