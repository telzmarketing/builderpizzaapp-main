# SaaS Multiempresa - Onda 3: clientes e pedidos

## Escopo comprovado

- clientes e privacidade: `customers`, `addresses`, `lgpd_policies`;
- identidade: `customer_auth`, `customer_channels`, `customer_preferences`;
- eventos: `customer_events`;
- venda: `orders`, `order_items`, `order_item_flavors`.

IDs, payloads e constraints globais existentes foram preservados. `admin_users`, pagamentos, cupons, salão, CRM, fidelidade e marketing não fazem parte desta onda.

## Inventário verificado no código

| Tabela | PK | Vínculos compostos adicionados | Unique tenant-scoped comprovada |
|---|---|---|---|
| `customers` | `id` | - | `email`; `google_id` quando preenchido |
| `addresses` | `id` | `customer_id -> customers` | - |
| `lgpd_policies` | `id` | - | - |
| `customer_auth` | `id` | `customer_id -> customers` | `(customer_id, auth_provider)`; `(auth_provider, identifier)` quando preenchido |
| `customer_channels` | `id` | `customer_id -> customers` | `(channel, normalized_identifier)` |
| `customer_preferences` | `id` | `customer_id -> customers` | `customer_id` |
| `orders` | `id` | `customer_id -> customers`; `address_id -> addresses` | `order_code`; `external_reference`, ambos quando preenchidos |
| `order_items` | `id` | `order_id -> orders`; `product_id -> products` | - |
| `order_item_flavors` | `id` | `order_item_id -> order_items`; `product_id -> products` | - |
| `customer_events` | `id` | `customer_id -> customers`; `order_id -> orders`; `product_id -> products` | - |

Todas essas tabelas, PKs e colunas foram confirmadas nos models atuais. `products (tenant_id, id)` é a referência de catálogo criada pela onda anterior.

## Cadeia Alembic

```text
20260725_tenant_domains
  -> 20260726_tenant_customers_orders_expand
  -> 20260727_tenant_customers_orders_backfill
```

`expand` adiciona `tenant_id` nullable e sem default, FK de tenant `NOT VALID`, índice unique `(tenant_id, id)`, uniques tenant-scoped comprovadas e FKs compostas `NOT VALID` nos vínculos deste slice e do catálogo já expandido.

`backfill` confirma o tenant legado, procura duplicatas das futuras chaves e rejeita ownership divergente antes de atribuir `tenant-legacy-default` apenas às linhas ainda nulas. O downgrade não apaga essa atribuição.

## Decisões e riscos

- Uniques globais legadas continuam ativas. Isso preserva compatibilidade, mas ainda impede reutilização entre tenants; removê-las pertence à futura fase `contract`.
- FKs `NOT VALID` protegem writes novos, mas o histórico depende do preflight e de futura `VALIDATE CONSTRAINT`.
- Não existe fallback ou default de tenant no schema/runtime.
- Relações com domínios ainda não tenantizados ficam intocadas até suas ondas.
- A identidade global do consumidor segue como decisão de produto aberta; os registros atuais são tratados como perfis operacionais tenant-owned, sem fusão entre empresas.

## Alinhamento ORM e runtime

Os dez models agora declaram `tenant_id` nullable, a FK direta nomeada para
`tenants`, o índice unique `(tenant_id, id)` e as uniques tenant-scoped da
migration `expand`. As uniques globais e FKs simples continuam declaradas para
preservar os contratos legados durante `expand/backfill`.

As FKs compostas permanecem deliberadamente na migration, que é a fonte de
integridade do PostgreSQL. Declará-las simultaneamente no metadata ORM criaria
dois caminhos de FK para os relacionamentos legados e exigiria trocar os joins
antes de todas as escritas carregarem `tenant_id`; isso quebraria a
compatibilidade com a flag desligada.

`TENANT_CUSTOMERS_ORDERS_ENFORCEMENT_ENABLED` nasce `False`. O helper
`customers_orders_enforcement_enabled()` apenas expõe esse gate ao fluxo
opt-in já existente em `tenant_ownership.py`. Nenhuma rota foi migrada nesta
etapa e, portanto, nenhuma rota deve ser apresentada como isolada ainda.

Pendências antes de ativar o gate:

- migrar cada leitura por ID/listagem para exigir `TenantContext` confiável e
  usar `scope_query_to_tenant`/`assert_resource_ownership`;
- atribuir tenant em toda criação com `assign_tenant_on_create`, incluindo
  checkout convidado, eventos e jobs;
- propagar ownership aos filhos e rejeitar pares parent/child divergentes;
- validar as FKs `NOT VALID` e executar testes PostgreSQL após o backfill;
- remover uniques globais somente na futura fase `contract`.

## Validação local

Sem Python/PostgreSQL local, a validação é estática: cadeia `revision/down_revision`, inspeção do código e `git diff --check`. Aplicação, `alembic heads/current/history`, counts e `VALIDATE CONSTRAINT` ficam para staging/VPS restaurada.
