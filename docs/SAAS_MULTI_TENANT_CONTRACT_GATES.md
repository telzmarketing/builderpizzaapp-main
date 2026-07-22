# SaaS multiempresa - gates da fase contract

## Status e limite desta entrega

Foram preparados cinco contracts, um por onda de dados:

1. `20260805_tenant_catalog_contract`;
2. `20260806_tenant_customers_orders_contract`;
3. `20260807_tenant_payments_contract`;
4. `20260808_tenant_operations_contract`;
5. `20260809_tenant_marketing_contract`;
6. `20260810_tenant_backoffice_contract`.

Eles ainda **não foram executados**. Cada migration aborta se encontrar `tenant_id`
nulo, igual a `default`, apontando para tenant inexistente ou soft-deleted. Somente
depois desse preflight ela valida as FKs multi-tenant `NOT VALID`, remove eventual
default da coluna e aplica `NOT NULL`.

Nenhum unique global legado é removido automaticamente. A presença do índice
tenant-scoped não prova que todos os writers já usam a chave composta, e nomes de
constraints podem divergir entre bancos criados por migration e por `create_all`.

## Grafo Alembic comprovado estaticamente

O inventário de 109 revisões encontrou zero revision IDs duplicados, zero pais
ausentes e um único head de arquivos: `20260810_tenant_backoffice_contract`.

Os quatro heads históricos citados são os pais de merges já existentes:

- `20260515_pay_on_delivery` e `20260515_product_promotion_benefits`, unidos por
  `20260516_store_notification_clear_after_view`;
- `20260610_delivery_radius_and_payment_retry` e
  `20260512_ads_pixel_event_defaults`, unidos por
  `20260613_marketing_intelligence_goals_timeline`.

Portanto, criar outra merge revision agora seria incorreto: não existem outros
heads de arquivo para incluir em um `down_revision` tuple. O instalador deve tratar
o banco físico separadamente, pois `alembic_version` pode ainda estar posicionado
em mais de um ancestral mesmo quando o grafo atual tem um só head.

## Gate obrigatório antes de cada contract

Executar na mesma release e no mesmo banco alvo:

```bash
alembic -c backend/alembic.ini heads --verbose
alembic -c backend/alembic.ini current --verbose
alembic -c backend/alembic.ini history --verbose
```

O `heads` deve mostrar apenas `20260810_tenant_backoffice_contract` no pacote a
ser instalado. O `current` deve ser registrado antes de qualquer upgrade. Não usar
`stamp`, não apagar linhas de `alembic_version` e não aplicar contract saltando os
respectivos expand/backfill.

Preflight físico geral:

```sql
SELECT table_schema, table_name
FROM information_schema.columns
WHERE column_name = 'tenant_id'
  AND table_schema = current_schema()
  AND is_nullable = 'YES'
ORDER BY table_name;

SELECT conrelid::regclass AS tabela, conname
FROM pg_constraint
WHERE contype = 'f' AND NOT convalidated
ORDER BY 1, 2;

SELECT schemaname, tablename, indexname, indexdef
FROM pg_indexes
WHERE schemaname = current_schema()
  AND indexdef ILIKE '%UNIQUE%'
ORDER BY tablename, indexname;
```

Para cada tabela listada na migration alvo, exigir contagem zero:

```sql
SELECT count(*) AS ownership_invalido
FROM <tabela> row
LEFT JOIN tenants tenant ON tenant.id = row.tenant_id
WHERE row.tenant_id IS NULL
   OR row.tenant_id = 'default'
   OR tenant.id IS NULL
   OR tenant.deleted_at IS NOT NULL;
```

Também registrar tamanho, volume e locks antes da janela:

```sql
SELECT relname, n_live_tup, n_dead_tup
FROM pg_stat_user_tables
WHERE relname IN (<tabelas_da_onda>)
ORDER BY n_live_tup DESC;

SELECT pid, relation::regclass, mode, granted
FROM pg_locks
WHERE relation IS NOT NULL AND NOT granted;
```

## Gate para remover uniques globais

Só criar uma migration posterior de drop após todos os itens abaixo:

- inventário do nome e definição reais em `pg_constraint` e `pg_indexes`;
- nenhum writer ativo usando lookup/upsert apenas pela chave global;
- ausência de duplicidade dentro de `(tenant_id, chave_de_negocio)`;
- teste A/B de dois tenants criando o mesmo valor de negócio;
- rollback definido para recriar a constraint global, reconhecendo que ele só será
  possível enquanto não existirem valores iguais entre tenants.

O drop deve citar nomes explícitos confirmados no banco. Não usar descoberta por
prefixo para remover constraints e não usar `DROP ... CASCADE`.

## Aplicação e rollback

Aplicar uma onda por janela, com backup/restauração testados e métricas de erro,
latência e cross-tenant acessíveis. Se o preflight embutido abortar, corrigir o
dado pela regra de negócio e repetir o preflight; não editar a migration nem
forçar `stamp`.

O downgrade dos contracts volta `tenant_id` a nullable, mas PostgreSQL não possui
operação equivalente para tornar uma FK validada novamente `NOT VALID`. Por isso,
o rollback operacional preferencial é restaurar a versão anterior da aplicação;
o downgrade de schema só deve ocorrer com decisão explícita e após verificar que
nenhum writer novo passou a depender do contrato.
