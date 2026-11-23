# back/painel-julia

Fase 4 da rodada 3 (#38): a Julia cuida do conteúdo sozinha, dentro do visual da marca (decisão: campos prontos, sem editor de blocos livre).
**Branch empilhada:** sai de `back/seguranca-auditoria` (PR #41), porque a migração nova vem depois da dele.

## O que mudou

| Área | Antes | Agora |
|---|---|---|
| Fotos de produto | Só "Tornar principal" | "Usar como capa", setas ← → e remover (`/admin/produtos/<id>/imagens/<id>/mover`) |
| Fotos de curso | Só remover (caixa no formulário); a primeira enviada era a capa para sempre | Capa, setas e remover embaixo do formulário (`/admin/cursos/<id>/fotos/<id>/mover` e `/excluir`) |
| Descrições | Um parágrafo só, sem quebra | Parágrafos, listas (`- `), **negrito** e *destaque* (filtro `texto_formatado`, sem HTML livre) |
| Destaque | A Início mostrava os mais novos; a loja ordenava por nome | `Product.destaque`: aparece primeiro na Início e na loja |
| Ordem | Cursos e serviços em ordem alfabética | `Course.ordem` e `Service.ordem` (menor primeiro; empate = alfabético) |
| Serviços | Só título e descrição | Foto (mesmo armazenamento das fotos de produto) e posição |
| Textos fixos | Slogan, Sobre nós e Peças personalizadas no HTML | Painel > Textos do site (`app/textos.py` + tabela `textos_site`) |

**Migração `a3c8e1f5b9d2`:**
- `products.destaque`, `courses.ordem`, `services.foto` e `services.ordem`, todos com `server_default`. As linhas que já existem ganham valores neutros (sem destaque, ordem 0, sem foto).
- Tabela nova `textos_site` (`chave`, `valor`, `atualizado_em`).

**Arquivos novos:**
- `app/services/ordem.py` (`mover`);
- `app/textos.py`;
- `app/blueprints/admin_textos.py`;
- `admin/textos.html`;
- macros `botao_acao` e `galeria_fotos` em `admin/_macros.html`.

## Por quê
- **Pedido do Adauto:** a Julia gerencia peças, produtos, cursos e serviços sem depender de nós.
- **Textos do site:** o slogan e o Sobre ainda são provisórios. Com eles editáveis, a Julia revisa quando quiser.
- **Segurança da formatação:** o texto é escapado antes de qualquer marca virar HTML. Nem `<script>` nem `<a href="javascript:">` digitados no painel chegam ao site, e a CSP do #41 continua sem `unsafe-inline`.
- **Textos do site guardados só quando mudam:** campo vazio volta ao original. Assim o padrão continua versionado no código, e o banco só guarda a escolha da Julia.

## Ajuda de formatação retirada (23/11)
- **Pedido do Adauto:** tirar do painel a caixa "Como formatar o texto" que ficava embaixo das descrições.
- **O que saiu:** `admin/_ajuda_texto.html`, os quatro `include` (produto, curso, serviço e Textos do site), o `aria-describedby` dos campos e as regras `.ajuda-texto` do `admin.css`.
- **O que ficou:** o filtro `texto_formatado`. Linha em branco continua virando parágrafo, e o que já foi escrito com `- ` ou `**` segue aparecendo certo no site.

## Correção de passagem
- **Rolagem lateral nos formulários do painel no celular.** Afetava os grupos com envio de arquivo, inclusive "Quem ensina" do curso, desde a Parte 4.
- **Causa:** `fieldset` e item de grid têm largura mínima igual ao conteúdo, e o campo de arquivo é largo.
- **Correção:** `min-width: 0` em `admin.css`.

## Como foi testado
- **`tests/test_painel_julia.py`:** 38 testes. Suíte inteira com **566 passando** (eram 528).
  - Reordenar: capa, setas, ação inválida dá 400, foto de outro produto ou curso dá 404, cliente comum dá 403.
  - Texto formatado e bloqueio de HTML.
  - Destaque na Início e na loja.
  - Ordem de cursos e serviços.
  - Foto de serviço: criar, trocar, remover e excluir, com o arquivo apagado do disco.
  - Textos do site: original, mudança, vazio volta ao original, limite de tamanho, HTML escapado, só admin.
- **Migração no SQLite:** upgrade, downgrade e upgrade, sem diferença entre o modelo e o banco.
- **Playwright em 390 e 1440:**
  - Trocar e desfazer a capa de um produto.
  - Galeria do curso.
  - Formulário de serviço com foto.
  - Mudar o slogan e voltar ao original.
  - Serviços e Sobre nós no site.
  - Sem rolagem lateral e sem erro no console.

## Como revisar
`git diff origin/back/seguranca-auditoria..origin/back/painel-julia`

## Riscos
- **Ordem dos produtos na loja:** agora começa pelos destaques. Sem nenhum destaque marcado, fica igual a antes.
- **Rota `/principal` da foto de produto:** continua existindo, por compatibilidade, e usa a mesma função das setas.
- **Botões das fotos no celular:** ficam grandes por causa do estilo atual dos botões do painel. O redesign dos painéis (Fase 5) resolve.
