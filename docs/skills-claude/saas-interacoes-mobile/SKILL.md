---
name: saas-interacoes-mobile
description: Use ao criar ou revisar interações no celular da loja Julia Malosti (Flask/Jinja) — menu gaveta, carrossel com deslizar, cartões clicáveis, feedback de toque, alvos de 44px e movimento reduzido.
---

# Interações no celular (loja Julia Malosti)

Objetivo: o site parecer app no celular sem framework, só HTML + `app/static/js/site.js` como
**melhoria progressiva**. Se o JS falhar, tudo continua navegável.

## 1. O HTML decide o que é clicável

| Quer que... | Use |
|---|---|
| cartão de produto leve à peça | `<a>` envolvendo foto + nome (já é assim em `shop/_cartao_produto.html`) |
| botão faça ação na mesma tela | `<button type="button">` |
| ação que muda dados (carrinho, sair) | `<form method="post">` + `csrf_token` + `<button type="submit">` |
| ícone sem texto | `aria-label` no `<a>`/`<button>` e `aria-hidden="true"` no SVG |

Nunca `div onclick`.

## 2. site.js: cada parte só roda se o elemento existir

O mesmo arquivo carrega em todas as páginas. Padrão:
```js
var banner = document.getElementById('inicio');
if (banner) carrossel(banner);   // carrossel só existe na home
```
Classe `js` no `<html>` liga estados que dependem de JS (topo transparente, `.revelar`).

## 3. Gestos

- Carrossel: troca com deslizar **só se** `|dx| > 50` e `|dx| > |dy| * 1.4` (senão é rolagem — solte).
- Listeners de toque `{ passive: true }` quando não há `preventDefault()`.
- Não usar a borda da tela (24 px): é do gesto nativo de voltar do iOS/Android.

## 4. Menu gaveta (≤ 1100 px)

- Botão com `aria-expanded` + `aria-controls`; texto do leitor alterna "Abrir/Fechar menu".
- Fecha com Esc e ao tocar num link.
- Sem JS: links ficam na linha (o botão nasce `hidden` e o JS revela).

## 5. Movimento

- Só `transform`/`opacity`. Nunca animar `width/height/top` (exceção: barra de progresso do carrossel).
- Entrada 220–320 ms `var(--ease-out)`; saída mais curta.
- `:active { transform: scale(.97) }` em tudo que é tocável; `-webkit-tap-highlight-color: transparent`.
- `prefers-reduced-motion`: carrossel começa pausado, `.revelar` aparece direto, sem zoom nas fotos.
- O que a pessoa vê toda hora (contador do carrinho, menu) não anima à toa.

## 6. Imagens leves

- Fotos em **WebP**, com `srcset` (800/1600) e versão retrato pro banner no celular.
- Primeira foto do banner com `fetchpriority="high"` + `preload`; as outras com `data-src` (baixam quando forem aparecer)
  ou `loading="lazy"`.
- Sempre `width`/`height` no `<img>` (evita a página pular enquanto carrega).

## 7. Como testar (Playwright + CDP)

```python
ctx = b.new_context(viewport={"width":390,"height":844}, has_touch=True, is_mobile=True)
cdp = ctx.new_cdp_session(pg)
cdp.send("Input.dispatchTouchEvent", {"type":"touchStart","touchPoints":[{"x":300,"y":400}]})
for i in range(1,13): cdp.send("Input.dispatchTouchEvent", {"type":"touchMove","touchPoints":[{"x":300-15*i,"y":400}]})
cdp.send("Input.dispatchTouchEvent", {"type":"touchEnd","touchPoints":[]})
```
Casos: deslizar longo troca a foto · vertical só rola · menu abre/fecha/Esc · `reduced_motion="reduce"`.
