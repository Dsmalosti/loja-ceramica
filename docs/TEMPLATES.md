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
| `/conta` | `account/conta.html` | (nenhuma por enquanto; pedidos entram na etapa do checkout) |
| `/carrinho/` (**exige login**) | `cart/carrinho.html` | `linhas` (cada uma com `.produto`, `.quantidade`, `.subtotal_centavos`), `total_centavos` |
| `/admin/` | `admin/dashboard.html` | `total_produtos`, `produtos_sem_estoque`, `total_cursos`, `total_servicos` |
| 404 / 403 | `errors/404.html`, `errors/403.html` | (nenhuma) |

Parciais: `shop/_cartao_produto.html` recebe a variável `produto` e é usado na home e na loja.

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

## Ainda por vir (o front já pode deixar o espaço)

- Checkout: botão "Finalizar compra" no carrinho (o espaço já está marcado em `cart/carrinho.html`).
- Lista de pedidos com status em `/conta`.
- Tela de pedidos no painel admin (as telas de produtos, categorias, cursos e serviços já existem, veja abaixo).
