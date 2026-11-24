# Compras e Suprimentos — Lote 1: Fundação

Status: implementado localmente; release e migration online pendentes de gate operacional.

## Entrega

- `PurchaseRequisition`: requisição tenant-scoped com versão concorrente.
- `PurchaseRequisitionItem`: itens vinculados a `InventoryItem` e `InventoryUnit`.
- `PurchaseRequisitionEvent`: histórico append-only de transições.
- Estados de requisição: rascunho, enviada, aprovada, sourcing, pedido, atendimento parcial, concluída, rejeitada e cancelada.
- Aprovação segregada: o solicitante não pode aprovar a própria requisição.
- Idempotência nas criações e transições críticas.
- Auditoria administrativa das operações.
- RBAC reutilizando o módulo `inventory` existente.
- Rotas oficiais sob `/api/gestao/purchases/requisitions`.

## Contratos

```text
POST  /api/gestao/purchases/requisitions
GET   /api/gestao/purchases/requisitions
GET   /api/gestao/purchases/requisitions/{id}
PUT   /api/gestao/purchases/requisitions/{id}
POST  /api/gestao/purchases/requisitions/{id}/submit
POST  /api/gestao/purchases/requisitions/{id}/approve
POST  /api/gestao/purchases/requisitions/{id}/reject
POST  /api/gestao/purchases/requisitions/{id}/cancel
POST  /api/gestao/purchases/requisitions/{id}/source
POST  /api/gestao/purchases/requisitions/{id}/order
```

As mutações críticas exigem `Idempotency-Key` e as transições exigem `expected_version`.

## Validação

- 14 testes focados aprovados.
- Compilação Python dos arquivos novos aprovada.
- Importação dos módulos novos aprovada.
- `git diff --check` sem erro nos arquivos do lote.
- Migration adicionada como `20261124_purchase_requisition_foundation`, dependente do head `20261122_print_agent_protocol`.

## Bloqueios conhecidos

- O banco atual está em `20261121_payment_amendment_settlement`, atrás do head.
- A renderização offline de toda a cadeia Alembic falha anteriormente, em `20261026_customer_phone_lgpd_scope.py`, por uso incompatível de `_OfflineScalarResult.first()`.
- Nenhuma migration foi aplicada online e nenhum deploy foi executado.
