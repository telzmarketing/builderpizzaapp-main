# Compras e Suprimentos - Lote 8: Hardening e Release

## Validacoes aprovadas

- estrutura, rotas, services, schemas, models e migrations revisados;
- cadeia Alembic com um unico head: `20261124_purchase_receipt_foundation`;
- 20 testes focados dos lotes 1 a 7 aprovados;
- compilacao Python e importacao do backend aprovados;
- `npm run typecheck` e `npm run build:client` aprovados;
- `git diff --check` aprovado;
- contrato da FK `fk_purchase_requisition_events_actor` alinhado entre model e migration.

## Gate de release

O release permanece bloqueado ate que o banco PostgreSQL seja atualizado de
`20261121_payment_amendment_settlement` para
`20261124_purchase_receipt_foundation` em ambiente controlado, com backup,
healthcheck e validacao ponta a ponta. Nenhuma migration ou deploy foi
executado automaticamente neste lote.

O checkout atual contem alteracoes e artefatos de outros trabalhos. A
publicacao deve usar um checkout/release imutavel contendo somente os arquivos
aprovados, sem limpeza destrutiva do workspace compartilhado.
