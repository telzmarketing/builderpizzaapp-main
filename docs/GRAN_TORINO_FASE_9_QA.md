# Gran Torino — Fase 9: QA de compras, notas, custos e contas a pagar

## Escopo auditado

A Fase 9 deve integrar compras, documentos fiscais, custos, contas a pagar e necessidades de reposição sem criar fontes paralelas. O cadastro de compras existente (`InventoryPurchase`) permanece a origem comercial da compra; o documento fiscal deve ser deduplicado por tenant, conferido antes da aprovação, e a obrigação financeira deve ser vinculada sem duplicação.

## Critérios de aceite

1. Compras, fornecedores, itens e documentos permanecem isolados por tenant.
2. XML repetido, chave de acesso repetida ou `Idempotency-Key` repetido não cria documento adicional.
3. Documento fiscal não aprovado não cria obrigação financeira nem entrada física.
4. Aprovação exige associação ou descarte explícito de todas as linhas.
5. A obrigação financeira deve ter parcelas explícitas, total positivo e vínculo auditável com o documento.
6. Repetir a reconciliação retorna a obrigação existente e não duplica transações ou parcelas.
7. Compra confirmada só gera conta a pagar quando a configuração de negócio estiver habilitada; o evento deve ser tenant-safe e idempotente.
8. Custos devem usar a operação canônica de estoque/CMV; não pode haver atualização paralela de saldo.
9. A necessidade de reposição deve considerar estoque disponível, reservas, lotes vencidos e demanda já programada; não foi localizada uma implementação completa desse motor nesta revisão.
10. Concorrência PostgreSQL deve produzir no máximo um documento, uma obrigação e suas parcelas por chave de negócio.

## Evidência executada

- `python -m pytest -q tests/test_finance_obligations.py tests/test_fiscal_receipt_xml.py tests/test_inventory_foundation.py tests/test_inventory_foundation_models.py tests/test_wave7_finance_context.py tests/test_wave7_inventory_context.py tests/test_tenant_background_events.py -p no:cacheprovider --basetemp=.runtime/qa-fase9`: **39 passed, 11 skipped**.
- O serviço de documentos possui escopo por `tenant_id`, deduplicação por hash/chave/idempotência, aprovação após associação de linhas e reconciliação financeira ligada por `receipt_document_id`.
- O serviço financeiro possui sincronização idempotente para compras confirmadas, condicionada às configurações de contas a pagar.

## Pendências e riscos que impedem liberar a fase

- `InventoryReceiptService.approve` apenas altera o documento para `validated`; não foi encontrada baixa/entrada física no ledger de estoque nem atualização de custo médio associada à aprovação.
- O upload e a reconciliação não demonstram lock/constraint testado em duas sessões PostgreSQL; há risco de corrida antes da restrição única ser aplicada.
- A reconciliação cria transações com fornecedor genérico e não usa, no fluxo mostrado, dados fiscais/parcelas do fornecedor para preencher a obrigação.
- Não foi localizada uma implementação completa de sugestão de reposição que calcule disponível, reservas, validade, lead time, lote mínimo e demanda já programada.
- Não há evidência nesta revisão de testes HTTP de RBAC/tenant cruzado, rollback induzido, migration aplicada em PostgreSQL real ou build da interface de compras/notas.

## Gate QA

A Fase 9 pode ser considerada concluída após implementar e provar a entrada física/custo na aprovação, o motor de reposição, concorrência PostgreSQL com rollback, isolamento HTTP entre tenants, migração a partir do head operacional e testes frontend end-to-end. A execução local atual comprova contratos e regras parciais, mas não libera produção.
