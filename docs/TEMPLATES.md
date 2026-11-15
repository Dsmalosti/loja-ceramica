# Contrato entre backend e front (templates)

Regra de ouro para não dar conflito no Git:

- **Front (templates e visual):** só mexe em `app/templates/` e `app/static/`.
- **Backend:** só mexe em `app/*.py`, `app/blueprints/`, `app/services/`, `config.py`, `migrations/`.

Se o front precisar de uma variável nova numa página, ele pede ao backend e a lista abaixo é atualizada no mesmo PR.

## Filtros e funções disponíveis em qualquer template

| Uso | O que faz |
|---|---|
| `{{ valor_em_centavos \| brl }}` | `5500` vira `R$ 55,00` |
| `{{ whatsapp_link('texto opcional') }}` | Link `wa.me` da loja (número de `WHATSAPP_NUMBER`, hoje `5512991399090`), com mensagem pré-preenchida. **Único jeito aceito** de linkar o WhatsApp: `wa.me/...` escrito à mão no template quebra um teste |
| `{{ image_url(imagem.caminho) }}` | URL da foto (aceita arquivo em `static/` ou URL completa) |
| `{{ site_name }}` | Nome da loja (vem de `SITE_NAME` no `.env`, hoje `Julia Malosti Arte Cerâmica`) |
| `{{ config.COURSES_FORM_URL }}` | Link do Google Forms dos cursos |
| `{{ csrf_token() }}` | Obrigatório em todo `<form method="post">`, num `<input type="hidden" name="csrf_token">` |
| `carrinho_qtd` | Quantidade de itens no carrinho (número; 0 se vazio), disponível em todos os templates |
| `current_user` | Usuário logado: `.is_authenticated`, `.nome`, `.email`, `.is_admin` |

Mensagens de aviso: o backend usa `flash(texto, "ok")` ou `flash(texto, "erro")`; o `base.html` já mostra.

## Páginas

| Rota | Template | Variáveis |
|---|---|---|
| `/` | `public/home.html` | `produtos_destaque` (até 4 produtos), `categorias` |
| `/loja/` e `/loja/?categoria=<slug>` | `shop/lista.html` | `produtos`, `categorias`, `categoria_atual` (ou `None`) |
| `/loja/<slug>` (**exige login**) | `shop/produto.html` | `produto` |
| `/cursos` | `public/cursos.html` | `cursos` |
| `/servicos` | `public/servicos.html` | `servicos` |
| `/pecas-personalizadas` | `public/pecas_personalizadas.html` | (nenhuma) |
| `/sobre` | `public/sobre.html` | (nenhuma) |
| `/contato` | `public/contato.html` | (nenhuma) |
| `/entrar` | `account/login.html` | `proximo` (destino após o login) |
| `/cadastro` | `account/cadastro.html` | `dados` (`nome` e `email` já digitados, para repreencher o formulário), `proximo` (destino após criar a conta; vai num `<input type="hidden" name="next">`) |
| `/conta` | `account/conta.html` | `ultimo_pedido` (ou `None`), `endereco` (ou `None`), `total_favoritos` |
| `/conta/dados` (POST de senha em `/conta/senha`) | `account/dados.html` | `valores` (`nome`, `email`, `telefone`) |
| `/conta/endereco` | `account/endereco.html` | `valores` (campos do endereço, `cep` já com hífen), `endereco` (ou `None`), `ufs` |
| `/conta/favoritos` | `account/favoritos.html` | `favoritos` (cada um com `.produto`) |
| `/conta/pedidos` | `account/pedidos.html` | `pedidos` |
| `/conta/pedidos/<id>` | `account/pedido.html` | `pedido` (só do dono; de outra pessoa = 404) |
| `/carrinho/` (**exige login**) | `cart/carrinho.html` | `linhas` (cada uma com `.produto`, `.quantidade`, `.subtotal_centavos`), `total_centavos` |
| `/admin/` | `admin/dashboard.html` | `total_produtos`, `produtos_sem_estoque`, `total_cursos`, `total_servicos`, `numeros` (`hoje_qtd`, `hoje_total`, `mes_qtd`, `mes_total`, `ticket_medio`, `aguardando`, `a_preparar`, `a_enviar`, `estoque_insuficiente`, `ultimos`) |
| `/admin/pedidos` | `admin/pedidos_lista.html` | `pedidos` (paginação: `.items`, `.page`, `.pages`, `.has_next`…), `contagens` ({status: n}), `filtros` (`status`, `q`), `rotulos` |
| `/admin/pedidos/<id>` | `admin/pedido_detalhe.html` | `pedido` (com `.usuario`, `.itens`, `.historico`), `acoes` ([(status, rótulo)] só as permitidas), `eventos`, `tem_estorno` |
| `POST /admin/pedidos/<id>/status` | (redireciona pro detalhe) | campo `status` |
| 404 / 403 | `errors/404.html`, `errors/403.html` | (nenhuma) |

Parciais: `shop/_cartao_produto.html` recebe a variável `produto` e é usado na home, na loja e nos favoritos.
`shop/_favoritar.html` (coração) recebe `produto` e, opcional, `com_texto=true` (página da peça).
`account/_menu_conta.html` é o menu das páginas da conta.

Funções e filtros novos: `favoritado(produto)` (bool; uma consulta por página) e `{{ data | data_br }}` /
`{{ data | data_br(true) }}` (horário de Brasília, com hora).

**pedido** (`Pedido`): `id`, `status`, `status_texto`, `subtotal_centavos`, `frete_centavos`, `total_centavos`,
`criado_em`, `quantidade_itens`, `itens` (cada um com `nome_produto`, `preco_unitario_centavos`, `quantidade`,
`subtotal_centavos`: **cópia do dia da compra**), `entrega_*` e `entrega_cep_formatado` (vazio = retirada).

**endereco** (`Endereco`): `cep`, `cep_formatado`, `logradouro`, `numero`, `complemento`, `bairro`, `cidade`, `uf`.

Favoritar: `POST /conta/favoritos/<produto_id>` com `acao` (`adicionar` ou `remover`, nunca "alternar") e `voltar`
(caminho interno para onde voltar). Visitante vê um link para o login no lugar do formulário.

## Campos dos objetos

**produto** (`Product`): `nome`, `slug`, `descricao`, `preco_centavos`, `estoque`, `disponivel` (ativo e com estoque), `categoria` (`.nome`, `.slug`), `imagens` (lista), `imagem_principal` (ou `None`).

**imagem** (`ProductImage`): `caminho`, `alt`.

**categoria** (`Category`): `nome`, `slug`.

**curso** (`Course`): `titulo`, `slug`, `descricao`, `valor_centavos` (pode ser `None`, "sob consulta"), `duracao`.

**servico** (`Service`): `titulo`, `descricao`.

## Carrinho

- **Exige login** (regra da Julia), em todas as rotas do blueprint. Sem login: GET volta pro mesmo endereço depois de entrar;
  POST de `cart.adicionar` volta pra página da peça; os outros POST voltam pra `/carrinho/`.
- Guardado na sessão. Sair da conta esvazia o carrinho (outra pessoa no mesmo computador não herda os itens).
  O preço e o estoque são sempre lidos do banco, nunca do formulário.
- Na `/loja/`, visitante sem login vê o aviso `.nota-login` com links de entrar/criar conta que voltam pro catálogo.
- Toda ação é um formulário POST com `csrf_token`: `cart.adicionar` (campo `quantidade`), `cart.atualizar` (`quantidade`; 0 remove), `cart.remover`, `cart.limpar`.
- CSS próprio em `app/static/css/carrinho.css` (também carregado na página do produto, para o formulário "Adicionar ao carrinho"). Pode redesenhar à vontade.
- Mensagens de estoque/indisponibilidade chegam por `flash` (`erro`/`ok`).

## Painel admin (CRUD)

Todos em `app/templates/admin/`, estendem `admin/base_admin.html` (menu do painel + bloco `admin`) e usam o CSS próprio `app/static/css/admin.css`, separado do `style.css` do site. O visual está provisório: pode redesenhar à vontade, mantendo os nomes de campos, `name=` dos inputs e o `csrf_token`.

| URL | Template | Variáveis |
|---|---|---|
| `/admin/categorias` | `categorias_lista.html` | `categorias` (cada uma com `.produtos`) |
| `/admin/categorias/nova`, `/<id>/editar` | `categoria_form.html` | `categoria` (`None` ao criar), `valores` (`nome`, `ativa`) |
| `/admin/produtos` | `produtos_lista.html` | `produtos`, `categorias`, `filtros` (`q`, `categoria`, `status`) |
| `/admin/produtos/novo`, `/<id>/editar` | `produto_form.html` | `produto` (`None` ao criar), `valores`, `categorias`, `max_imagens` |
| `/admin/cursos` | `cursos_lista.html` | `cursos` |
| `/admin/cursos/novo`, `/<id>/editar` | `curso_form.html` | `curso` (`None` ao criar), `valores` |
| `/admin/servicos` | `servicos_lista.html` | `servicos` |
| `/admin/servicos/novo`, `/<id>/editar` | `servico_form.html` | `servico` (`None` ao criar), `valores` |
| erro 413 | `errors/413.html` | (nenhuma) |

Regras que o front precisa respeitar:

- Todo `<form method="post">` leva `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">`. Sem isso o servidor recusa.
- Formulários com foto usam `enctype="multipart/form-data"` e o campo `name="imagens"` (aceita vários arquivos).
- Botões de ação (ativar/desativar, excluir, foto principal) são formulários POST. Use o macro `botao_post` de `admin/_macros.html` em vez de links.
- `valores` traz o que a pessoa digitou (para repreencher o formulário após erro): preço em `valores.preco_texto`, estoque em `valores.estoque_texto`.
- Mensagens de sucesso/erro chegam pelo `flash` (categorias `ok` e `erro`), já exibidas no `base.html`.
- Fotos enviadas ficam em `app/static/uploads/produtos/` e o caminho salvo no banco começa com `uploads/produtos/`. Use sempre `image_url(imagem.caminho)`.

## Promoções (preço)

O preço final vem de **um único lugar** (`app/services/precos.py`). Nos templates:

| Uso | O que faz |
|---|---|
| `{% set info = preco(produto) %}` | `info.original`, `info.final`, `info.tem_desconto`, `info.selo` ("−20%" / "−R$ 10,00"), `info.promocao` (`.nome`, `.fim`) |
| `{% set info = preco_curso(curso) %}` | igual; curso "sob consulta" vem com `info.final` = `None` |
| `{% from "shop/_preco.html" import mostrar_preco %}` `{{ mostrar_preco(info) }}` | `<p class="preco">` com o antigo riscado (`.preco__antigo`) e o novo (`.preco__novo`), com texto "De … por …" pra leitor de tela |

- Nunca mostrar `produto.preco_centavos` direto pro cliente: use `preco(produto)`.
- Carrinho: cada `linha` tem `preco_unitario_centavos` (já com desconto) e `preco` (o objeto acima).
- Pedido: `item.preco_original_centavos` (só quando houve desconto) para mostrar "de R$ 55 por R$ 44".
- Cartão: selo `.selo.selo--promo` em cima à esquerda da foto (o coração fica à direita; "Indisponível" embaixo).

Painel: `/admin/promocoes` (`promocoes_lista.html`: `promocoes`), `/admin/promocoes/nova` e `/<id>/editar`
(`promocao_form.html`: `promocao`, `valores`, `produtos`, `cursos`). Campos: `nome`, `tipo` (`percentual`/`valor`),
`percentual`, `valor`, `inicio`/`fim` (`datetime-local`, horário de Brasília), `produtos` e `cursos` (vários), `ativa`.

## Checkout (Mercado Pago, Checkout Pro)

| Rota | Template | Variáveis |
|---|---|---|
| `/checkout/` (exige login) | `checkout/resumo.html` | `linhas` (como no carrinho), `subtotal_centavos`, `frete_centavos` (frete fixo), `endereco` (ou `None`), `token` (uso único), `pagamento_disponivel` |
| `POST /checkout/confirmar` | (redireciona pro Mercado Pago) | campos `token`, `entrega` (`retirada` ou `entrega`), `csrf_token` |
| `POST /checkout/pagar/<pedido_id>` | (redireciona pro Mercado Pago) | botão "Pagar agora" de pedido aguardando |
| `/checkout/retorno/<pedido_id>` | `checkout/retorno.html` | `pedido` (status já confirmado com o Mercado Pago) |

- O form do resumo tem `id="checkout"` com `data-subtotal` e `data-frete`; o `site.js` só **mostra** o total
  (`#checkout-frete`, `#checkout-total`). O valor cobrado é sempre calculado no servidor.
- Nunca colocar campo de cartão em template nosso: o pagamento é na página do Mercado Pago.
- `pedido.entrega_tipo` (`retirada`/`entrega`), `pedido.pago_em`. `estoque_insuficiente` é interno (painel).

Funções novas (painel): `whatsapp_cliente(telefone, texto)` (link pro WhatsApp do **cliente**; '' sem telefone),
`{{ telefone | telefone }}` ('12991112222' → '(12) 99111-2222'), `rotulo_origem(h.origem)` (Cliente, Mercado Pago, Painel).
