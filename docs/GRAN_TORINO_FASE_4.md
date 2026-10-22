# Gran Torino — Fase 4: Rastreabilidade

## Entrega

- Lotes existentes passam a registrar abertura auditável, responsável, regra aplicada e validade resultante.
- A validade após abertura nunca pode ampliar a validade original do lote.
- Operações de abertura são idempotentes, versionadas e tenant-safe.
- Genealogia entre lotes registra origem, destino, operação, quantidade, unidade e responsável.
- FEFO permanece decidido no backend: lotes disponíveis são ordenados pela validade efetiva e lotes vencidos, bloqueados ou em quarentena não são elegíveis.
- A tela de estoque exibe lotes, validade efetiva, estado e abertura, com feedback de carregamento, erro e vazio.
- O head Alembic operacional é `20261022_inventory_traceability`.

## Limites

Etiquetas físicas e impressão reaproveitam a infraestrutura existente; esta fase não declara prova de impressão em hardware nem deploy em VPS. Transformações de cozinha e estoque preparado pertencem à Fase 5.
