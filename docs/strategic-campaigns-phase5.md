# Campanhas Estratégicas — Fase 5: Comercialização controlada

## Entrega

- A campanha agora possui configuração comercial persistida e versionada:
  `immediate` ou `preorder`, venda com loja fechada, agendamento obrigatório,
  antecedência mínima/máxima e meios de pagamento permitidos.
- O quote e a criação definitiva do pedido aplicam as mesmas regras no backend.
- Campanhas autorizadas podem aceitar pedidos agendados mesmo quando a loja
  convencional está fechada, sem alterar a configuração operacional global.
- O checkout público carrega a configuração publicada e exibe o agendamento
  para pré-venda mesmo quando a loja está aberta.
- A configuração é incluída no snapshot publicado da campanha.

## Gate de segurança

Esta fase não habilita ainda limite de quantidade, reservas comerciais ou
capacidade por faixa. Esses recursos exigem reserva transacional tenant-scoped,
idempotência, locks/constraints, liberação no cancelamento/expiração e gate para
que pedidos futuros só entrem no KDS e consumam estoque na janela operacional.

## Evidências locais

- `alembic -c backend/alembic.ini heads` — `20261125_strategic_campaign_commercial_phase5`.
- `npm.cmd run typecheck` — aprovado.
- `python -m pytest tests/test_strategic_campaign_phase1.py -q` — 7 testes aprovados.
- `python -m py_compile` dos serviços/modelos alterados — aprovado.
- `git diff --check` — aprovado.

Migration, commit, push, deploy e execução em banco real permanecem pendentes.
