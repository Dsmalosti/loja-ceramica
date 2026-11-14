# Loja Julia Malosti Arte Cerâmica

Site institucional + loja + painel da Julia. Backend Flask (Diogo), front em templates Jinja.

## Regras do projeto
- Front mexe só em `app/templates/` e `app/static/`. Arquivos `.py` são do Diogo: mudança de backend
  só com explicação, aval do Adauto e revisão do Diogo.
- Não inventar ferramenta nem dependência nova: usar o que o projeto já tem (Flask, Jinja, CSS/JS puros).
- Contrato dos templates: `docs/TEMPLATES.md` (variáveis que cada página recebe).
- Trabalhar em branch `front/<assunto>`; o Diogo revisa e faz o merge na `main`.
- Antes de entregar: skill `saas-qa-release` (pytest + Playwright + prints). Segurança: `saas-flask-seguranca`.
  Interações no celular: `saas-interacoes-mobile`.

## Skills do projeto
As skills ficam versionadas em `docs/skills-claude/`. Se `.claude/skills/` ainda não existir,
copie cada pasta de `docs/skills-claude/<nome>/` para `.claude/skills/<nome>/` antes de começar.

## Marca
- Cores: mocha `#5B4632`, âmbar `#C8792C`, champanhe `#F4D9A0`, fundos creme/areia (tokens em `static/css/style.css`).
- Fontes: Cormorant Garamond (títulos) e DM Sans (textos).
- Imagens sempre em WebP e o mais leves possível (`static/img/inicio/`).
- Contatos: WhatsApp +55 12 99139-9090 · Instagram @malosti.loja · Rua Espanha, 532 - Jardim das Nações.

## Funil
A home é a antiga landing: cada botão leva pra uma página interna
(Ver as peças → `/loja/`, Ver os cursos → `/cursos`, Encomendar → `/pecas-personalizadas` → WhatsApp).
O CTA principal da Julia é o WhatsApp.

## Pendências conhecidas
- Detalhe do produto ainda sem `@login_required` (regra: só logado vê detalhes e compra).
- Slogan e texto do Sobre são provisórios (a Julia vai revisar).
- Fotos enviadas pelo painel precisam de storage externo em produção (Vercel tem disco efêmero).
- Checkout Mercado Pago, wishlist, histórico de pedidos e promoções ainda não existem.
