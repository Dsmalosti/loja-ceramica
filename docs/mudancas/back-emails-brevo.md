# back/emails-brevo

Fase 2 da rodada 3 (#38). Sai da `main`, não depende do PR #37.

## O que mudou
- **`app/services/email.py`:** `enviar()` ganhou `responder_para` e todo e-mail sai com `replyTo`. Sem o parâmetro, a resposta vai para o `EMAIL_REMETENTE` (o ateliê).
- **`app/services/mensagens.py`:** o aviso de pedido pago para a Julia usa `responder_para=<e-mail da cliente>`. Assim, quando a Julia clica em Responder, a mensagem vai direto para quem comprou.
- **Modelos em `app/templates/email/`:**
  - Logo em texto no topo.
  - Prévia que aparece na caixa de entrada, ao lado do assunto.
  - Rodapé com endereço, WhatsApp e Instagram do ateliê.
  - Na retirada, a linha "Frete: Grátis" saiu, e o e-mail do cliente mostra onde e quando retirar e pede o número do pedido.
  - O e-mail da Julia ganhou o botão "WhatsApp da cliente" quando há telefone cadastrado.

## Por quê
- O remetente é `@gmail.com`. O Brevo não autentica domínio gratuito e troca o "De" por um endereço dele (`...t-sender-sib.com`). Sem `replyTo`, a resposta do cliente podia não chegar ao ateliê.
- "Frete: Grátis" num pedido de retirada confundia o cliente: parecia que haveria entrega.

## Como era antes
- Não havia `replyTo` no corpo enviado ao Brevo.
- O e-mail do pedido dizia só "Sua retirada é no ateliê" e o horário, sem endereço e sem contato.

## Como foi testado
- `tests/test_email.py`: 4 testes novos.
  - A resposta vai para o ateliê por padrão.
  - A resposta pode ir para outra pessoa.
  - O aviso da Julia responde para a cliente.
  - O e-mail da retirada traz endereço, horário e número do pedido, sem linha de frete.
- Suíte inteira: 504 testes passando (antes eram 500).
- Prints dos três e-mails em 390 e 700 px, sem estourar a largura.

## Como revisar
`git diff origin/main..origin/back/emails-brevo`

## Riscos
- E-mails continuam nunca derrubando compra nem cadastro: `enviar()` segue sem lançar erro.
- Nenhuma variável de ambiente nova. O Render já tem as que o código usa.
