# Gran Torino — Fase 5: Cozinha e preparo

## Entrega

- Receitas operacionais versionadas com insumo, unidade, rendimento e instruções.
- Ordens de preparo tenant-safe com estados, programação, aprovação, pausa, bloqueio e cancelamento.
- Apontamentos incrementais idempotentes de produção, perda e descarte.
- Interface administrativa e operacional integrada à área de Estoque.
- Head Alembic operacional: `20261022_preparation_execution`.

## Limite de validação

O ciclo de transformação ainda requer a integração transacional final com o ledger físico: débito dos lotes de origem, crédito do lote preparado e genealogia no mesmo commit. Por isso, a Fase 5 está implementada como base operacional, mas não deve ser liberada como transformação de estoque concluída antes desse gate PostgreSQL.
