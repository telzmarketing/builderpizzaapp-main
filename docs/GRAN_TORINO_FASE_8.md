# Gran Torino — Fase 8: consumo por tentativa KDS

## Entrega

- Cada tentativa física registra linhas imutáveis de consumo por insumo.
- O consumo usa o snapshot CMV congelado do item e o ledger canônico de estoque.
- A baixa ocorre na finalização da montagem, dentro da transação da tentativa.
- Operações e movimentos são associados à tentativa e protegidos por idempotência.
- A API retorna modo de consumo, operação e revisão do snapshot para o painel KDS.
- Migration operacional: `20261022_kds_attempt_consumption`.

## Limites

A integração foi validada localmente. Concorrência real em PostgreSQL, rollback induzido, isolamento HTTP entre tenants e reconciliação completa com o consumo legado ainda precisam de evidência antes da liberação produtiva.
