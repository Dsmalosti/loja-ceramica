# back/melhor-envio

Frete pelo Melhor Envio (issues #44 e #30), aprovado pelo Adauto: **cotação e frete no pedido**. A etiqueta, por enquanto, a Julia compra no site do Melhor Envio com os dados do pedido.
**Branch empilhada:** sai de `front/sobre-e-carrossel` (PR #45). A migração nova vem depois da `a3c8e1f5b9d2` (#42).

## O que mudou

| Onde | Antes | Agora |
|---|---|---|
| `app/services/melhorenvio.py` (novo) | — | `cotar(cep, linhas)` chama `POST /api/v2/me/shipment/calculate` com medidas em cm, peso em kg e valor declarado por unidade. Usa `custom_price` e `custom_delivery_time`, ignora serviço com `error` e ordena do mais barato para o mais caro. `cotar_sem_erro` devolve a mensagem para a tela. Só usa `urllib`. |
| `checkout.resumo` | Só retirada | Com o token no `.env`: "Retirar no ateliê" ou "Receber em casa" (`?entrega=casa`, por link e sem JS). Cota com o endereço salvo da pessoa e guarda na sessão o preço que ela viu. |
| `checkout.confirmar` | Recusava `entrega` | Aceita `entrega` quando o Melhor Envio está configurado. **Cota de novo:** o preço nunca vem do formulário. Recusa serviço que não veio na cotação e avisa se o frete mudou desde o resumo. Copia o endereço para o pedido e grava `frete_servico` e `frete_prazo_dias`. |
| `Pedido` (migração `c1d9e4a7f3b6`) | — | `frete_servico` (texto) e `frete_prazo_dias` (inteiro), os dois opcionais |
| `cliente.endereco` | Voltava sempre para a própria tela | Aceita `next` (só caminho interno, via `destino_seguro`) para voltar ao checkout |
| Telas | — | Resumo com as opções de frete e o total que acompanha a escolha (`site.js`; o servidor recalcula de qualquer jeito). Pedido e painel mostram o serviço e o prazo. A página do produto avisa que o frete é calculado pelo CEP. |
| Config | — | `MELHOR_ENVIO_TOKEN`, `MELHOR_ENVIO_AMBIENTE` (sandbox ou producao), `MELHOR_ENVIO_CEP_ORIGEM`, `MELHOR_ENVIO_USER_AGENT` e `MELHOR_ENVIO_SERVICOS`, em `config.py`, `.env.example` e `render.yaml` (`sync: false`) |

## Por quê
- **A transportadora era pendência da #30:** os produtos para cerâmica já tinham peso e medidas desde o PR #33.
- **Cotação de novo na confirmação:** é a mesma regra do preço dos produtos. Ninguém consegue pagar menos frete editando o formulário.
- **Sem token, nada muda:** o checkout continua só com retirada. Por isso a integração pode entrar antes da conta do ateliê existir.

## Como foi testado
- `tests/test_melhor_envio.py`: 21 testes, com a API simulada (nada sai para a internet).
  - O corpo enviado para a API (medidas, peso em kg, valor e quantidade).
  - Leitura da resposta (preço em texto, serviço com erro, ordem).
  - Produto sem medidas e CEP inválido.
  - URL do sandbox com o token e o User-Agent.
  - Resumo sem endereço e com opções.
  - Pedido com frete, endereço e serviço, e o item "Frete" na preferência do Mercado Pago.
  - Serviço não cotado recusado, frete que mudou, API fora do ar e entrega sem endereço.
  - Retirada sem frete, `next` do endereço (inclusive link externo ignorado) e texto do produto.
- Suíte inteira: **587 passando** (eram 566).
- Migração no SQLite: upgrade, downgrade e upgrade, sem diferença.
- Playwright em 390 e 1440 com a cotação simulada: total inicial e total depois de trocar o serviço, opções com 44 px e sem rolagem lateral.

## Como revisar
`git diff origin/front/sobre-e-carrossel..origin/back/melhor-envio`

## Riscos e o que falta
- **Não testado contra a API real.** Sem token não deu para chamar nem o sandbox. O formato segue a documentação oficial (docs.melhorenvio.com.br). Com o token do sandbox, fazer uma compra de teste ponta a ponta.
- **Escopo do token:** a documentação lida não diz qual escopo a cotação exige. Conferir ao gerar o token.
- **Um só ponto de origem:** o `MELHOR_ENVIO_CEP_ORIGEM` define de qual unidade os envios saem.
- **Etiqueta:** não é gerada pelo site. A Julia compra no painel do Melhor Envio com os dados do pedido.
- **E-mails da compra:** já mostram o frete (a linha "Frete" aparece quando não é retirada), mas ainda não citam o nome do serviço. Isso fica para depois do merge do #39, para não conflitar.
