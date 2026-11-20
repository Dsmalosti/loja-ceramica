# back/compra-por-loja

Sai de `back/duas-lojas` (PR #32). Parte 3 de 4 da reformulação (#29).

## O que mudou
- O detalhe do produto abre sem login. O login só é pedido para comprar pelo site ou favoritar.
- **Peças:** a compra é fechada pelo WhatsApp. O botão vira "Comprar" ou "Encomendar pelo WhatsApp", e o servidor recusa peça no carrinho (`cart.adicionar` e `carrinho.vendavel`).
- **Produtos para cerâmica:** carrinho e checkout como antes, mas só com retirada no ateliê. A opção de entrega com frete fixo saiu do resumo, da rota `confirmar`, do `config.py` e do `.env.example`.
- `Product` ganha `peso_gramas`, `altura_cm`, `largura_cm` e `comprimento_cm`, obrigatórios no painel quando a categoria é da loja de produtos.
- Horário de retirada, endereço, prazo das peças (30 a 40 dias), troca em 10 dias e o que fazer quando o item chega com problema ficam em `app/templates/_atelie.html`. Eles aparecem no produto, no checkout, no retorno, no pedido, no e-mail, em Sobre nós e em Serviços.
- A demo usa pedidos só de produtos e com retirada. Os produtos da demo ganham peso e medidas.
- `render.yaml` pede `EMAIL_AVISO_PEDIDOS` com `sync: false`. O valor fica só no painel do Render.

## Por quê
Respostas da Julia: peças são fechadas pelo WhatsApp e produtos pelo site. Não há entrega em casa. A transportadora ainda vai ser escolhida (#30) e vai precisar de peso e medidas para cotar o frete.

## Como era
Qualquer produto ia para o carrinho. O detalhe pedia login. O checkout oferecia entrega com frete fixo de R$ 25.

## O que NÃO saiu
Os campos de entrega do `Pedido` (`entrega_tipo`, `entrega_*`, `frete_centavos`), o status `enviado` e a cobrança de frete no Mercado Pago continuam no código. Pedidos antigos seguem funcionando, e a transportadora vai usar essas partes.

## Migração
`d4e8a1c07b52`: quatro colunas inteiras e opcionais em `products`. Subida e descida testadas no SQLite. No Postgres só conferi o SQL gerado.

## Como foi testado
- `tests/test_compra_por_loja.py` (24 testes). O `catalogo` do `conftest` agora é da loja de produtos, porque é ele que vai para o carrinho nos testes antigos.
- Playwright: visitante na peça e no produto, cadastro de conta de teste, checkout e o formulário do painel.

## Como revisar
```bash
git diff origin/back/duas-lojas..origin/back/compra-por-loja
```

## Riscos
- Produtos para cerâmica já cadastrados sem peso e medidas só passam a exigir esses campos quando alguém editar o produto.
- Quem tinha uma peça no carrinho antes do deploy vê o aviso de que ela saiu do carrinho.
