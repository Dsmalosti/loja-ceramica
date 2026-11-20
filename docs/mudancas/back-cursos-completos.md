# back/cursos-completos

Sai de `back/compra-por-loja` (PR #33). Parte 4 de 4 da reformulação (#29).

## O que mudou
- `Course` ganha `turma_aberta`, `professor_nome`, `professor_instagram` (só o perfil, sem @) e `professor_foto`, além da propriedade `instagram_url`.
- Tabela nova `course_images` (`CourseImage`): até 6 fotos por curso, no mesmo armazenamento das fotos de produto (disco local ou Cloudinary).
- No painel, o formulário de curso aceita turma aberta ou fechada, quem ensina (nome, @ ou link do Instagram e foto) e fotos. Na edição dá para remover fotos e trocar ou apagar a foto de quem ensina, tudo no mesmo envio. A lista do painel mostra a turma.
- Na página `/cursos`, cada curso tem fotos que deslizam, o selo da turma, quem ensina com link do Instagram, o botão do formulário e o do WhatsApp. Com a turma fechada, o formulário vira "Entrar na lista de espera".
- `validators.parse_instagram`: aceita `@perfil`, `perfil` ou link do perfil e recusa o resto (outro site, `javascript:`, espaço, mais de 30 caracteres).
- Na demo, uma turma fica fechada, todos os cursos ganham fotos, e quem ensina aparece como "Equipe Malosti".

## Por quê
A Julia quer avisar quando a turma está fechada sem perder o interessado: o formulário e o WhatsApp continuam disponíveis nos dois casos.

## Como era
O curso tinha só título, descrição, duração, valor e ativo. A página mostrava uma arte decorativa e um único botão.

## Segurança
- Fotos validadas pelo conteúdo, com a mesma função das fotos de produto. Todas são validadas antes de gravar qualquer arquivo.
- `remover_fotos` só aceita foto do próprio curso (teste com id de outro curso).
- Arquivos antigos são apagados depois do commit. Se o banco recusar, os arquivos novos são apagados.
- O Instagram vira sempre `https://www.instagram.com/<perfil>`: o link nunca vem do formulário.

## Migração
`e5f9b2c3d6a1`: 4 colunas em `courses` (padrão `true`/`''`) e a tabela `course_images` com índice. Subida e descida testadas no SQLite. No Postgres só conferi o SQL gerado.

## Como revisar
```bash
git diff origin/back/compra-por-loja..origin/back/cursos-completos
```

## Riscos
- As fotos de curso ficam na mesma pasta das de produto (`uploads/produtos/` ou a pasta do Cloudinary). Isso funciona, mas o nome da pasta ficou genérico.
- Em produção sem Cloudinary, as fotos somem a cada deploy, igual às de produto (#16).
