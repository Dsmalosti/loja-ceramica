# Contrato entre backend e front (templates)

Regra de ouro para não dar conflito no Git:

- **Front (templates e visual):** só mexe em `app/templates/` e `app/static/`.
- **Backend:** só mexe em `app/*.py`, `app/blueprints/`, `app/services/`, `config.py`, `migrations/`.

Se o front precisar de uma variável nova numa página, ele pede ao backend e a lista abaixo é atualizada no mesmo PR.

## Filtros e funções disponíveis em qualquer template

| Uso | O que faz |
|---|---|
| `{{ valor_em_centavos \| brl }}` | `5500` vira `R$ 55,00` |
| `{{ whatsapp_link('texto opcional') }}` | Link `wa.me` da loja, com mensagem pré-preenchida |
| `{{ image_url(imagem.caminho) }}` | URL da foto (aceita arquivo em `static/` ou URL completa) |
| `{{ site_name }}` | Nome da loja (vem do `.env`) |
| `{{ config.COURSES_FORM_URL }}` | Link do Google Forms dos cursos |
| `{{ csrf_token() }}` | Obrigatório em todo `<form method="post">`, num `<input type="hidden" name="csrf_token">` |
| `current_user` | Usuário logado: `.is_authenticated`, `.nome`, `.email`, `.is_admin` |

Mensagens de aviso: o backend usa `flash(texto, "ok")` ou `flash(texto, "erro")`; o `base.html` já mostra.

## Páginas

| Rota | Template | Variáveis |
|---|---|---|
| `/` | `public/home.html` | `produtos_destaque` (até 4 produtos), `categorias` |
| `/loja/` e `/loja/?categoria=<slug>` | `shop/lista.html` | `produtos`, `categorias`, `categoria_atual` (ou `None`) |
| `/loja/<slug>` | `shop/produto.html` | `produto` |
| `/cursos` | `public/cursos.html` | `cursos` |
| `/servicos` | `public/servicos.html` | `servicos` |
| `/pecas-personalizadas` | `public/pecas_personalizadas.html` | (nenhuma) |
| `/sobre` | `public/sobre.html` | (nenhuma) |
| `/contato` | `public/contato.html` | (nenhuma) |
| `/entrar` | `account/login.html` | `proximo` (destino após o login) |
| `/cadastro` | `account/cadastro.html` | `dados` (`nome` e `email` já digitados, para repreencher o formulário) |
| `/conta` | `account/conta.html` | (nenhuma por enquanto; pedidos entram na etapa do checkout) |
| `/admin/` | `admin/dashboard.html` | `total_produtos`, `produtos_sem_estoque`, `total_cursos`, `total_servicos` |
| 404 / 403 | `errors/404.html`, `errors/403.html` | (nenhuma) |

Parciais: `shop/_cartao_produto.html` recebe a variável `produto` e é usado na home e na loja.

## Campos dos objetos

**produto** (`Product`): `nome`, `slug`, `descricao`, `preco_centavos`, `estoque`, `disponivel` (ativo e com estoque), `categoria` (`.nome`, `.slug`), `imagens` (lista), `imagem_principal` (ou `None`).

**imagem** (`ProductImage`): `caminho`, `alt`.

**categoria** (`Category`): `nome`, `slug`.

**curso** (`Course`): `titulo`, `slug`, `descricao`, `valor_centavos` (pode ser `None`, "sob consulta"), `duracao`.

**servico** (`Service`): `titulo`, `descricao`.

## Ainda por vir (o front já pode deixar o espaço)

- Botão "Adicionar ao carrinho" na página do produto, página do carrinho e checkout.
- Lista de pedidos com status em `/conta`.
- Telas de cadastro do painel admin (produtos, categorias, cursos, serviços, pedidos).
