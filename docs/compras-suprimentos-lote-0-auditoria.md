# Compras e Suprimentos — Lote 0: Auditoria e Contratos

Data da auditoria: 2026-11-23
Status: concluído como auditoria read-only; implementação bloqueada até os gates abaixo serem atendidos.

## Objetivo

Fechar o diagnóstico técnico e os contratos necessários para evoluir Compras e Suprimentos sem criar estoque, fornecedores, financeiro, CMV ou fluxo de recebimento paralelo.

## Estrutura reutilizável

- Insumos: `InventoryItem`, unidades, categorias, locais, lotes, reservas e saldos.
- Fornecedor operacional: `InventorySupplier`.
- Compras existentes: `InventoryPurchase` e `InventoryPurchaseItem`.
- Estoque: `InventoryOperation` e `InventoryStockMovement`.
- Recebimento fiscal: `InventoryReceiptDocument` e `InventoryReceiptDocumentLine`.
- Financeiro: `FinanceObligation`, parcelas, `FinanceTransaction` e `FinanceCounterparty`.
- Receitas e porcionamento: `InventoryRecipeVersion`, `InventoryRecipeItem`, `inventory_portion`, `preparation` e `pcp`.
- Segurança: `TenantContext`, RBAC server-side e `require_rbac_permission`.
- Idempotência: `IdempotencyService` e chaves compostas por tenant.
- Frontend: `client/lib/api.ts` e telas existentes de Gestão/Estoque/Financeiro/CMV.

## Gaps confirmados

Ainda não existe contrato completo para:

1. requisição formal com estados e aprovação;
2. cotação com múltiplas propostas e conversão de unidades;
3. aprovação segregada por alçada;
4. revisão imutável de pedido;
5. recebimento operacional separado do documento fiscal;
6. postagem idempotente de estoque por recebimento;
7. vínculo único entre recebimento, documento fiscal e obrigação financeira;
8. dashboard de compras com estados pendente, estimado e confirmado.

## Decisões de contrato

- `InventorySupplier` é o fornecedor operacional canônico.
- A contraparte financeira deve ser vinculada explicitamente a esse fornecedor; não haverá associação por nome, documento solto ou texto livre.
- Pedido aprovado não movimenta estoque e não cria obrigação financeira.
- Recebimento operacional aprovado autoriza a postagem no estoque.
- A obrigação financeira somente nasce após recebimento aprovado e reconciliação conforme a política fiscal do tenant.
- Documento fiscal e conferência física são eventos relacionados, mas distintos.
- Unidades devem usar unidade-base e conversão versionada; conversão ausente ou ambígua bloqueia.
- Eventos confirmados são imutáveis; correções usam reversão ou novo evento.
- O tenant vem exclusivamente do contexto autenticado no backend.
- Dados financeiros novos devem usar `NUMERIC`/`Decimal`.

## Estados propostos

### Requisição

`DRAFT → SUBMITTED → APPROVED → SOURCING → ORDERED → PARTIALLY_FULFILLED → FULFILLED`

`SUBMITTED → REJECTED` e `DRAFT/SUBMITTED/APPROVED → CANCELLED`.

### Cotação

`DRAFT → OPEN → CLOSED → AWARDED`.

`DRAFT/OPEN → CANCELLED`.

### Pedido de compra

`DRAFT → PENDING_APPROVAL → APPROVED → PARTIALLY_RECEIVED → RECEIVED`.

`PENDING_APPROVAL → REJECTED` e `DRAFT/PENDING_APPROVAL/APPROVED → CANCELLED`.

### Recebimento operacional

`DRAFT → SUBMITTED → APPROVED → POSTED → COMPLETED`.

`SUBMITTED → REJECTED`, `APPROVED → PENDING_DOCUMENT` e `POSTED → REVERSED`.

## Invariantes obrigatórios

- Toda nova entidade possui `tenant_id NOT NULL`.
- FKs entre entidades carregam também a fronteira de tenant.
- O solicitante não pode aprovar o próprio pedido.
- Quantidade recebida nunca excede o saldo autorizado.
- Uma origem não pode gerar duas postagens de estoque.
- Uma origem não pode gerar duas obrigações financeiras.
- Retry retorna o resultado original sem duplicar efeitos.
- Cancelamento não apaga histórico nem desfaz recebimento já realizado.
- CMV histórico não é alterado silenciosamente.
- Falha em qualquer etapa deixa a transação sem efeitos parciais.

## Evidências da auditoria

- Rotas existentes: `/gestao/inventory`, `/gestao/inventory/v1/documents`, `/gestao/finance` e `/gestao/cmv`.
- Banco atual: revisão `20261121_payment_amendment_settlement`.
- Head Alembic: `20261122_print_agent_protocol`.
- `alembic check`: bloqueado porque o banco não está atualizado.
- Testes focados executados: `23 passed` em estoque, recebimentos, financeiro, CMV, tenant e unidades.
- Os testes emitiram apenas avisos de depreciação do Pydantic e permissão de escrita no cache do pytest.

## Bloqueadores antes do Lote 1

1. Confirmar a semântica publicada de `InventoryPurchase`.
2. Confirmar o vínculo fornecedor operacional/contraparte financeira.
3. Ratificar quando a obrigação financeira é criada.
4. Ratificar se documento fiscal é obrigatório para concluir recebimento.
5. Confirmar unidade-base e política de conversão.
6. Confirmar política de custeio e arredondamento do CMV.
7. Atualizar o baseline Alembic por procedimento operacional autorizado.
8. Especificar constraints, locks e chaves de idempotência da nova fundação.

Nenhum código, modelo, migration ou banco foi alterado neste lote.
