# Gran Torino — Fase 3

## Escopo entregue

- Importação privada e autenticada de NF-e/NFC-e XML para conferência de entrada.
- Parser limitado a 5 MiB, sem DTD/ENTITY, com hash SHA-256, chave de acesso e identificação do emitente.
- Idempotência por tenant, hash e chave de acesso; o XML não gera estoque automaticamente.
- Associação explícita das linhas aos insumos e aprovação documental separada do recebimento físico.
- Obrigações financeiras em `NUMERIC(20,2)`, com parcelas e vencimentos somente quando informados pelo operador.
- Espelhamento das parcelas em lançamentos financeiros existentes, sem pagamento automático.

## Migration

`20261022_inventory_receipt_documents` é filha de `20261021_inventory_recipe_details`.
`20261022_finance_fiscal_obligations` é o head operacional único.

## Validação local

- Parser fiscal: 8 testes aprovados.
- Obrigações financeiras e contexto tenant: testes aprovados.
- Compilação Python (`compileall`) e `git diff --check` aprovados.
- Frontend: 19 testes de API e build Vite aprovados.

PostgreSQL descartável e validação ponta a ponta em ambiente real permanecem como gate operacional de release; esta fase não executa deploy.
