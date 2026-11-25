# Campanhas Estratégicas — Fase 6: Integrações operacionais

## Entrega

- Pedidos agendados futuros deixam de aparecer nas filas de cozinha e no
  overview operacional do KDS.
- O início de preparação é rejeitado pelo KDS e pelo `OrderService` enquanto a
  janela programada não tiver começado.
- A aprovação do pagamento continua registrada normalmente, mas o consumo de
  estoque é adiado para a janela operacional.
- Quando o pedido entra em preparação, o fluxo canônico existente realiza o
  consumo idempotente de estoque e mantém os snapshots de CMV.
- O filtro é tenant-scoped e preserva o checkout, pagamento e financeiro já
  existentes.

## Gate de segurança

Esta fase não cria ainda capacidade comercial, reservas por faixa, job de
liberação automática ou dashboard financeiro específico da campanha. Esses
componentes dependem de uma reserva transacional com lock, idempotência,
cancelamento/expiração e reconciliação. O pedido pago futuro permanece visível
no histórico e financeiro, mas fora da operação produtiva até o horário devido.

## Evidências locais

- `npm.cmd run typecheck` — aprovado.
- `python -m py_compile` dos serviços alterados — aprovado.
- `python -m pytest tests/test_strategic_campaign_phase1.py tests/test_strategic_campaign_phase6.py -q` — aprovado.
- `git diff --check` — aprovado.

Não foram executados migration em banco, commit, push ou deploy.
