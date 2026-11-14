---
name: saas-qa-release
description: Use antes de entregar qualquer mudança de front da loja Julia Malosti (Flask/Jinja) — pytest, varredura de rotas por perfil, Playwright em 360/390/768/1440, console limpo, screenshots e checklist do PR pro Diogo.
---

# QA e entrega de front (loja Julia Malosti · Flask + Jinja)

"Funciona na minha máquina" não é critério. Critério é: **testes verdes, todas as rotas em todos os
perfis, só mudou o que foi pedido, nenhum erro no console, layout conferido no celular e no desktop**.

## 0. Testes do Diogo (sempre primeiro)

```bash
pytest -q
```
Antes de mexer, anote quantos passam (base atual: 197). Depois de mexer, tem que dar o mesmo número.
Alguns testes conferem texto do HTML — ex.: `"Carrinho (2)" in client.get("/")`. Antes de mudar
cabeçalho, botão ou mensagem, rode `grep -n "in html\|get_data" tests/*.py` pra ver o que é conferido.

## 1. Dados de exemplo local

```bash
export FLASK_APP=wsgi.py
flask init-db && flask seed
flask create-admin --nome "Admin" --email admin@exemplo.test --password "<gerar com secrets.token_urlsafe>"
flask run
```
Nunca repita a senha no chat; guarde num arquivo fora do git.

## 2. Varredura de rotas por perfil

Perfis: **anônimo**, **cliente** (criar pelo `/cadastro` local), **admin**.

| Perfil | Rotas |
|---|---|
| anônimo | `/ /loja/ /loja/<slug> /cursos /servicos /sobre /contato /pecas-personalizadas /carrinho/ /entrar /cadastro` |
| cliente | as acima + `/conta` + fluxo adicionar ao carrinho → `/carrinho/` |
| admin | `/admin/ /admin/produtos /admin/produtos/novo /admin/categorias /admin/cursos /admin/cursos/novo /admin/servicos` |

Falha = status fora de 200/302, ou 302 onde devia abrir (ex.: admin mandado pra `/entrar`).

## 3. Playwright (navegador real)

- Celular 360 e 390 (`has_touch=True, is_mobile=True`), tablet 768, desktop 1440.
- `page.on("pageerror")` + `console` tipo `error` → lista vazia. (Fonte do Google bloqueada pela rede
  do ambiente de teste não conta; código nosso sim.)
- `document.documentElement.scrollWidth <= clientWidth` em toda página (nada estoura a largura).
  Atenção a `position:absolute` (ex.: texto pra leitor de tela) escapando de área com `overflow`.
- Alvos de toque ≥ 44 px no celular (links no meio de frase são exceção aceita).
- **Funil da home**: cada botão leva pra página interna certa — Ver as peças → `/loja/`,
  Ver os cursos → `/cursos`, Encomendar/Pedir personalizada → `/pecas-personalizadas`,
  inscrição em curso → formulário (se `COURSES_FORM_URL` configurado) ou WhatsApp com o nome do curso.
- Home: topo transparente no banner e sólido depois; WhatsApp flutuante escondido enquanto o banner aparece;
  carrossel avança, pausa e respeita `reduced_motion="reduce"` (botão vira "Continuar").
- Menu do celular abre, fecha com Esc e ao tocar num link.

## 4. Olhar de verdade

Screenshot das telas alteradas (390 e 1440) e **abrir a imagem**. Elementos com `.revelar` animam ao
rolar: antes do print, adicione `visivel` e espere ~1 s, senão sai tudo apagado.

## 5. Entrega (fluxo do projeto)

1. Front só mexe em `app/templates/` e `app/static/`. Arquivo `.py` é do Diogo: mudança de backend
   só com explicação e aval do Adauto, e revisão do Diogo.
2. Branch própria (`front/<assunto>`), nunca commit direto na `main`.
3. Commit com mensagem em português dizendo o quê e por quê.
4. PR pro Diogo com: o que mudou, como testar, prints, pendências.
5. O Diogo revisa e faz o merge na `main`.
6. Entregáveis de apresentação vão pro Drive em `Saas Ceramica - Julia Malosti/Claude Outputs/<data> - <assunto>/`.
