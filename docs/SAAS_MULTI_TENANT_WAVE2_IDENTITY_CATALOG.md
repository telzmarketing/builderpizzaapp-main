# SaaS Multiempresa — Onda 2: Identidade/RBAC e Catálogo

Estado: migrations de expansão e backfill criadas, sem execução local.
Tenant legado: tenant-legacy-default.

## Decisão arquitetural

A identidade administrativa admin_users permanece global e o acesso a empresas continua em tenant_memberships. Os catálogos rbac_modules e rbac_permissions também permanecem globais.

Somente tabelas comprovadamente operacionais recebem ownership nesta onda. Não há NOT NULL, remoção de unique legado, validação de FK nem contract.

## Inventário exato

Identidade/RBAC operacional, 4 tabelas em backend/models/rbac.py:

- roles
- role_permissions
- user_permissions
- admin_audit_logs

Catálogo, ofertas e apresentação, 21 tabelas:

- products, product_categories, product_sizes, product_crust_types, product_drink_variants, best_seller_config, multi_flavors_config
- product_promotions, product_promotion_combinations, promotions, promotion_landing_pages
- campaigns, campaign_products, promotional_kits, promotional_kit_items
- upsells, upsell_metrics, upsell_events, order_upsells
- home_catalog_config, theme_settings

Total: 25 tabelas tenant-owned.

## Expand

Migration 20260723_tenant_catalog_expand:

- adiciona tenant_id nullable e sem default;
- adiciona FK para tenants.id como PostgreSQL NOT VALID;
- cria unique index (tenant_id, id) para preparar FKs compostas futuras;
- cria uniques tenant-scoped para roles.name, product_categories.name, campaigns.slug, promotion_landing_pages.slug e upsell_metrics.upsell_id.

As uniques globais atuais permanecem. Isso preserva compatibilidade, mas ainda bloqueia repetição entre tenants até o contract.

## Backfill

Migration 20260724_tenant_catalog_backfill:

- exige a existência ativa do tenant legado;
- verifica duplicatas das cinco novas uniques antes de qualquer UPDATE;
- atualiza somente tenant_id IS NULL;
- usa bind parameter para o tenant;
- não sobrescreve ownership existente;
- não apaga atribuição no downgrade.

## Dependências, riscos e gates

- A seed 20260722_legacy_tenant_seed deve preceder o backfill.
- Models e services ainda precisam da etapa dual-compatible antes do isolamento runtime.
- Índices serão criados na transação Alembic; o deploy futuro precisa considerar o volume físico.
- order_upsells recebe ownership agora, mas a relação com orders será endurecida na onda de pedidos.
- Sem PostgreSQL local, não foram executados Alembic, backfill ou validações físicas.

## Models e adoção runtime dual-compatible

Os 25 models operacionais agora refletem o schema de expansão: `tenant_id`
nullable, FK nomeada, índice único `(tenant_id, id)` e as cinco constraints
tenant-scoped. As constraints globais legadas permanecem deliberadamente.

O helper `backend/core/tenant_ownership.py` permite que cada rota seja migrada
com contexto confiável, filtro exato de tenant, atribuição no create e validação
de ownership em lookup por ID. O gate
`TENANT_IDENTITY_CATALOG_ENFORCEMENT_ENABLED` é independente da autenticação e
permanece `false` por padrão.

Estado de isolamento: **ainda não ativo**. Nenhuma rota ou service de RBAC,
produtos, promoções, campanhas, upsell, home ou tema foi globalmente filtrada
nesta etapa. Enquanto o gate estiver desligado, queries e creates conservam o
comportamento legado. Mesmo com o gate ligado, somente callers que adotarem o
helper estarão isolados; habilitar o flag antes de migrar todos os caminhos de
leitura e escrita do slice é proibido.

Antes de contract: backup restaurável, zero NULL, zero tenant órfão, zero relação cruzada, análise de duplicatas, regressão A/B e validação das FKs.
