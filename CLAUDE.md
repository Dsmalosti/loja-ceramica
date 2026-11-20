# Malosti Arte Cerâmica

Site do ateliê de Julia e Alexandre Malosti: escola, peças, produtos para ceramistas e painel. Backend Flask (Diogo), front em templates Jinja.

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
- Cores: fundo `#F6F1EA`, marrom `#463123`, preto `#000000`, âmbar `#AD770F` (tokens em `static/css/style.css`).
- Fontes: Cormorant Garamond (títulos) e DM Sans (textos).
- Imagens sempre em WebP e o mais leves possível (`static/img/inicio/`).
- Contatos: WhatsApp +55 12 99139-9090 · Instagram @malosti.loja · Rua Espanha, 532 - Jardim das Nações.

## Funil
A home é a antiga landing: cada botão leva pra uma página interna
(cada foto do carrossel tem chamada e destino próprios: peças, produtos para cerâmica e cursos).
O CTA principal da Julia é o WhatsApp.

## Pendências conhecidas
- Slogan e texto do Sobre são provisórios (a Julia vai revisar).
- Fotos enviadas pelo painel precisam de storage externo em produção (Vercel tem disco efêmero).
- Checkout (Mercado Pago), favoritos, histórico de pedidos, promoções e e-mails (Brevo) já existem; falta testar o
  pagamento no sandbox com o site publicado e configurar o Brevo no servidor.
