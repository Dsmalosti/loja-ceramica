# back/duas-lojas

Sai de `front/identidade-atelie` (PR #31). Parte 2 de 4 da reformulação (#29).

## O que mudou
- `Category.loja`: cada categoria pertence à loja `pecas` ou `produtos`. As constantes ficam em `app/lojas.py`.
- `/loja/` abre em peças. `?loja=produtos` abre a outra loja. `?categoria=<slug>` decide a loja sozinha, então links antigos continuam certos.
- `?q=` busca no nome, na descrição e na categoria, só dentro da loja aberta.
- Início: Saídas do forno só com peças, faixa de Produtos para cerâmica e atalhos só de categorias de peças. Cada faixa mostra até 8 itens.
- `/contato` e `/pecas-personalizadas` respondem 301 para `/sobre#contato` e `/servicos#personalizadas`. Os dois templates saíram.
- Painel: campo Loja na categoria, coluna Loja na lista e categorias agrupadas por loja no cadastro de produto.
- `SITE_NAME` padrão: "Malosti Arte Cerâmica".
- Demo: 5 itens fictícios em 2 categorias da loja de produtos.

## Por quê
O ateliê vende dois tipos de coisa, com regras de compra diferentes (a Parte 3 usa esta separação). A loja fica na categoria, e não no produto, para a Julia decidir uma vez só e não existir produto em categoria da loja errada.

## Como era
Uma loja só, com todas as categorias e sem busca. A Início pegava os 4 produtos mais novos de qualquer tipo.

## Decisão para revisar
A busca filtra em Python, não em SQL. Assim "ceramica" encontra "Cerâmica" igual no SQLite e no Postgres, sem a extensão `unaccent`. A lista da loja já é carregada inteira, e o catálogo é pequeno. Se passar de alguns milhares de itens, vale trocar por busca no banco.

## Migração
`c7a1f4e92d30`: coluna `loja` com padrão `pecas` e constraint `ck_categories_loja`. Categorias existentes ficam em peças. O `downgrade` remove as duas.

## Como foi testado
- `tests/test_duas_lojas.py` (37 testes) e a suíte completa.
- Migração: sobe, `flask db check`, desce e sobe de novo no SQLite. Para o Postgres só conferi o SQL gerado em modo offline; ela não rodou num Postgres real.
- Playwright em 360, 390, 768 e 1440: abas, busca, filtro, redirecionamentos, console e largura.

## Como revisar
```bash
git diff origin/front/identidade-atelie..origin/back/duas-lojas
```

## Riscos
- Depois do deploy, categorias de produtos precisam ser criadas ou movidas no painel; até lá a loja de produtos fica vazia.
- O detalhe da peça continua exigindo login. A Parte 3 abre o detalhe e separa a compra por loja.
