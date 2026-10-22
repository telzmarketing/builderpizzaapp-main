# Gran Torino — Fase 7: KDS multioperador

## Entrega

- Unidades físicas e tentativas de preparo com estados versionados.
- Fila individual e fila geral por tenant.
- Presença operacional e heartbeat de estação.
- Comandos de montagem, forno, conferência e refazimento.
- Redistribuição gerencial com motivo, operador disponível e versões esperadas.
- Painel responsivo com timers baseados nos timestamps do servidor.
- Migration `20261022_kds_production`, head operacional atual.

## Limites

O pedido comercial continua sendo a autoridade dos estados de venda. Consumo detalhado por tentativa e integração completa entre KDS e estoque pertencem à Fase 8; esta fase não deve ser liberada como prova de consumo transacional sem PostgreSQL concorrente.
