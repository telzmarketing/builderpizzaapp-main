# Auditoria SaaS Multiempresa — Fase 0

> Data da auditoria: 2026-07-21
> Estado: concluída no código; validação física do PostgreSQL e da VPS pendente
> Escopo: documentação e desenho técnico, sem implementação multi-tenant

## 1. Resumo executivo

O sistema atual é um monólito compartilhado React + FastAPI + SQLAlchemy/PostgreSQL, funcional como operação monoempresa. A transformação para SaaS multiempresa é viável sem criar aplicação, build, serviço ou banco por empresa, mas o isolamento ainda não existe no núcleo.

Achados quantitativos:

- 38 arquivos em `backend/models`;
- 160 declarações ORM nesses arquivos;
- 36 declarações ORM adicionais dentro de arquivos de rota;
- 196 declarações `__tablename__` rastreadas no código;
- 52 arquivos de rotas e aproximadamente 680 handlers FastAPI;
- 59 arquivos de services;
- aproximadamente 897 queries ORM explícitas e 284 referências a SQL textual nos principais caminhos;
- 88 migrations Alembic e um SQL avulso;
- somente 36 das 160 tabelas dos models possuem `tenant_id`, todas sem FK para uma entidade `tenants` e concentradas em módulos periféricos.

Conclusão: `tenant_id=default` é apenas um rótulo legado. Não pode ser considerado isolamento e não pode ser usado como fallback de requisição. A Fase 1 permanece bloqueada até os gates da seção 17 serem aprovados.

## 2. Decisões arquiteturais

1. Uma aplicação, um frontend, um backend e um PostgreSQL compartilhado.
2. Dados operacionais recebem `tenant_id` obrigatório após migração `expand → backfill → validate → contract`.
3. O domínio principal da plataforma hospeda login, painel das empresas e painel master.
4. Domínios e subdomínios próprios carregam somente as experiências públicas.
5. Subdomínio automático da plataforma não é requisito da primeira entrega; poderá ser capacidade futura configurável.
6. Painel resolve tenant por JWT/sessão e membership validado; público resolve por hostname ativo; webhook por credencial/evento persistido; job por payload interno assinado.
7. `tenant_id` de body, query, header ou URL nunca é autoridade.
8. Host desconhecido falha fechado ou recebe landing neutra; nunca recebe o tenant legado.
9. Billing SaaS será um domínio separado dos pagamentos dos pedidos.
10. Alembic deverá se tornar a única autoridade de schema antes do primeiro rollout multiempresa.

## 3. Arquitetura atual e lacunas

### 3.1 Backend

- FastAPI em `backend/main.py`, com muitos routers registrados com e sem `/api` por compatibilidade.
- SQLAlchemy em `backend/models`, mas parte dos models/schemas/regras ainda está dentro de arquivos de rota.
- Regras principais em `backend/services`, com SQL ORM e SQL textual legado.
- `backend/main.py` executa `create_all_tables()` e `_run_migrations()` no startup.
- `_run_migrations()` contém DDL manual e captura exceções amplamente, podendo mascarar drift.

### 3.2 Frontend

- SPA centralizada em `client/App.tsx`.
- API oficial centralizada em `client/lib/api.ts`.
- Painel protegido por `AdminGuard` e `AdminLayout`.
- Experiência delivery/salão é selecionada no frontend por `client/lib/experience.ts`; isso não constitui resolução segura de tenant.
- PWA/Service Worker possui caches de shell, estáticos e mídia que precisarão de testes de troca de host e empresa.

### 3.3 Infraestrutura

- O checkout não contém arquivos versionados de Nginx, units systemd, Docker/Compose ou workflow completo de deploy.
- A topologia descrita é Nginx → Node/Express e FastAPI → PostgreSQL, mas os server blocks, headers, TLS, diretórios persistentes e envs reais precisam ser capturados na VPS/staging.
- Não é permitido prometer resolução de host, SSL ou rollback operacional antes desse snapshot.

## 4. Autenticação, usuários e RBAC

Estado comprovado:

- `get_current_admin` extrai apenas `sub` e busca `AdminUser.id` global em `backend/routes/admin_auth.py`.
- JWT de login inclui dados do usuário e `role_id`, mas não membership ou contexto de empresa confiável.
- `AdminUser.role_id` é nullable e seu vínculo é aplicado no nível da aplicação.
- `backend/routes/rbac.py` considera usuário sem role como master legado.
- Roles, permissões, overrides e auditoria são globais.
- Logout é stateless, sem catálogo de sessões/revogação.
- `backend/config.py` possui fallback de desenvolvimento para o segredo JWT; produção deve falhar no boot quando segredo seguro não estiver configurado.

Modelo proposto para a fundação:

- `tenants`;
- `tenant_memberships`, unique `(tenant_id, user_id)`;
- `platform_roles` e permissões globais explícitas;
- roles operacionais vinculadas ao membership/tenant;
- sessões/revogação quando necessário;
- auditoria append-only;
- migração explícita do master legado, removendo a regra “role nula = master”.

`TenantContext` mínimo:

```text
tenant_id
actor_user_id
membership_id
tenant_role
platform_role opcional
source: panel | public_host | webhook | job
request_id / correlation_id
```

Sem membership ativa: `403`. Recurso válido de outro tenant: `404`, reduzindo enumeração.

## 5. Inventário e classificação das tabelas

### 5.1 Globais da plataforma

- `admin_users`: identidade global; acesso operacional migra para membership.
- `rbac_modules`: catálogo global de capacidades.
- `rbac_permissions`: catálogo global de permissões.

Novas tabelas globais previstas: `tenants`, `platform_roles`, catálogo de features, planos, assinaturas, billing SaaS, domínios e auditoria de plataforma. Elas ainda não existem.

### 5.2 Compartilhada com controle

- `geocode_cache`: pode permanecer compartilhada se a chave for normalizada, não contiver PII bruta e possuir TTL. Se armazenar endereço identificável, deve ser tenantizada.

### 5.3 Tenant-owned — catálogo, comercial e aparência

`products`, `product_categories`, `product_sizes`, `product_crust_types`, `product_drink_variants`, `best_seller_config`, `multi_flavors_config`, `product_promotions`, `product_promotion_combinations`, `promotions`, `promotion_landing_pages`, `campaigns`, `campaign_products`, `promotional_kits`, `promotional_kit_items`, `upsells`, `upsell_metrics`, `upsell_events`, `order_upsells`, `home_catalog_config`, `theme_settings`.

### 5.4 Tenant-owned — clientes, CRM, identidade e LGPD

`customers`, `addresses`, `lgpd_policies`, `customer_auth`, `customer_channels`, `customer_preferences`, `customer_events`, `customer_tags`, `customer_tag_assignments`, `customer_segments`, `customer_ai_profiles`, `customer_ai_suggestions`, `customer_ai_analysis_jobs`.

### 5.5 Tenant-owned — pedidos e pagamentos

`orders`, `order_items`, `order_item_flavors`, `payments`, `payment_events`, `payment_provider_customers`, `payment_gateway_config`.

### 5.6 Tenant-owned — fidelidade e cupons

`loyalty_levels`, `loyalty_rewards`, `loyalty_rules`, `loyalty_settings`, `loyalty_benefits`, `loyalty_benefit_usage`, `loyalty_cycles`, `referrals`, `customer_loyalty`, `loyalty_transactions`, `coupons`, `coupon_usages`.

### 5.7 Tenant-owned — operação, frete, entrega, salão e notificações

`logistics_settings`, `delivery_persons`, `deliveries`, `delivery_events`, `delivery_earnings`, `shipping_config`, `freight_type_configs`, `shipping_neighborhoods`, `shipping_cep_ranges`, `shipping_distance_rules`, `shipping_order_value_tiers`, `shipping_promotions`, `shipping_extra_rules`, `shipping_zones`, `shipping_zone_areas`, `shipping_rules`, `restaurant_tables`, `reservations`, `table_sessions`, `table_session_items`, `salao_page_settings`, `store_operation_settings`, `store_weekly_schedules`, `store_operation_intervals`, `store_operation_exceptions`, `store_operation_logs`, `store_notification_settings`, `store_notifications`, `store_notification_days`, `store_notification_impressions`, `store_notification_captured`.

### 5.8 Tenant-owned — marketing, tráfego e BI

`traffic_campaigns`, `campaign_creatives`, `campaign_links`, `tracking_sessions`, `tracking_events`, `ad_platform_integrations`, `ad_accounts`, `ad_campaigns_external`, `ad_daily_metrics`, `campaign_settings`, `ad_sync_logs`, `business_insights`, `product_performance`, `marketing_goals`, `marketing_timeline_events`.

### 5.9 Tenant-owned — chatbot, Agente WhatsApp e gateway

`chatbot_settings`, `chatbot_faq`, `chatbot_conversations`, `chatbot_messages`, `chatbot_automations`, `chatbot_handoffs`, `chatbot_knowledge_docs`, `agente_whatsapp_sessions`, `agente_whatsapp_ai_settings`, `agente_whatsapp_channel_settings`, `agente_whatsapp_messages`, `agente_whatsapp_audio_artifacts`, `agente_whatsapp_processing_jobs`, `agente_whatsapp_outbox`, `agente_whatsapp_provider_states`, `agente_whatsapp_internal_alerts`, `agente_whatsapp_events`, `agente_whatsapp_context`, `agente_whatsapp_tool_calls`, `agente_whatsapp_metrics`, `agente_whatsapp_campaigns`, `agente_whatsapp_stories`, `whatsapp_gateway_instances`, `whatsapp_gateway_logs`, `whatsapp_gateway_update_logs`, `whatsapp_gateway_scheduler_settings`.

### 5.10 Tenant-owned — estoque, CMV, financeiro e fiscal

`gestao_module_settings`, `inventory_units`, `inventory_categories`, `inventory_locations`, `inventory_suppliers`, `inventory_items`, `inventory_purchases`, `inventory_purchase_items`, `inventory_manual_entries`, `inventory_stock_movements`, `inventory_recipe_versions`, `inventory_recipe_items`, `order_cmv_snapshots`, `order_item_cmv_snapshots`, `order_item_cmv_ingredient_snapshots`, `finance_accounts`, `finance_categories`, `finance_counterparties`, `finance_transactions`, `finance_settlements`, `fiscal_companies`, `fiscal_certificates`, `fiscal_series`, `fiscal_product_profiles`, `fiscal_documents`, `fiscal_document_items`, `fiscal_document_events`.

### 5.11 Tenant-owned — autorização e auditoria operacional

`roles`, `role_permissions`, `user_permissions`, `admin_audit_logs`.

### 5.12 Models declarados em rotas

Também foram rastreadas tabelas em `ads_oauth.py`, `automations.py`, `crm.py`, `email_marketing.py`, `exit_popup.py`, `marketing.py` e `whatsapp_marketing.py`, incluindo ads OAuth/campanhas/pixels, pipelines/cards/tarefas CRM, listas/campanhas/configs de Email e WhatsApp, automações, tracking, visitantes e integrações. Todas são tenant-owned, exceto estados OAuth efêmeros que ainda precisam ser vinculados ao tenant e à sessão. O catálogo físico deve confirmar todas antes da primeira migration.

## 6. Cobertura atual de tenant

As 36 tabelas com coluna existente concentram-se em CMV, CRM, estoque, gestão, fiscal, financeiro, WhatsApp Gateway e operação da loja. Problemas:

- default literal `default`;
- ausência de FK para `tenants`;
- tipos divergentes `String(80|100)`;
- índices simples sem o padrão real da consulta;
- tabelas filhas do mesmo domínio ainda sem tenant;
- services e schemas aceitando ou injetando o valor default.

Essas colunas não devem ser removidas ou sobrescritas. A Fase 1 deverá mapear valores distintos, converter `default` para o UUID do tenant legado e reconciliar filhos antes de aplicar constraints.

## 7. Uniques, FKs e índices críticos

Unicidades a revisar como tenant-compostas: email/google de cliente conforme decisão de identidade, nome de categoria, slug de campanha/landing, código de cupom, número de mesa, email do entregador, `order_code`, `external_reference`, IDs de pagamento/provider, sessão de chatbot, referral code, tipo de frete, plataforma de integração, dedupe/idempotência do Agente WhatsApp e chaves de BI.

Podem permanecer globais: email da identidade administrativa, `rbac_modules.key`, `rbac_permissions.key`, hostname público e identificadores verdadeiramente globais do provider quando comprovado.

Todas as relações entre entidades tenant-owned precisam impedir cruzamento. Padrão preferido:

```text
pai: UNIQUE (tenant_id, id)
filho: FOREIGN KEY (tenant_id, parent_id)
       REFERENCES pai (tenant_id, id)
```

Prioridades: pedido→cliente/endereço/cupom/mesa; item→pedido/produto; pagamento→pedido; campanha→lista/produto; entrega→pedido/motoboy; CRM→cliente; estoque/CMV/financeiro/fiscal; salão; chatbot e WhatsApp.

Índices devem refletir queries reais: `(tenant_id, status)`, `(tenant_id, created_at DESC)`, `(tenant_id, customer_id)`, `(tenant_id, order_id)` e uniques compostas. Índice isolado em `tenant_id` não é suficiente.

## 8. Queries e risco de IDOR

O volume de consultas impede correção manual sem inventário automatizado. Núcleo de alto risco:

- `Product`, `Customer`, `Order` e `Payment` não possuem tenant;
- centenas de rotas recebem `{id}` e consultam apenas pelo identificador;
- webhooks localizam pagamentos e pedidos por IDs externos globais;
- SQL textual precisa ser revisado separadamente dos helpers ORM.

Padrão da Fase 1/2:

- dependency central resolve `TenantContext`;
- services recebem contexto obrigatório;
- criação força `tenant_id=context.tenant_id`;
- listagem e busca usam tenant + recurso;
- tentativa de forjar tenant é rejeitada ou ignorada;
- repositories/helpers explícitos podem reduzir esquecimento;
- filtro global “mágico” não será adotado sem testes extensivos.

## 9. Webhooks, credenciais, uploads, caches e jobs

### 9.1 Webhooks

Mercado Pago e ASAAS possuem validações e idempotência parcial, mas gateway config e lookups permanecem globais. Fluxo futuro:

1. resolver tenant por endpoint público não previsível, conta/credencial ou metadata persistida;
2. carregar segredo daquele tenant;
3. validar assinatura;
4. persistir evento unique `(tenant_id, provider, event_id)`;
5. buscar pagamento por `(tenant_id, provider, provider_payment_id)`;
6. processar e auditar dentro do contexto.

### 9.2 Credenciais

`PaymentGatewayConfig`, IA, chatbot e Agente WhatsApp armazenam segredos em configurações globais ou texto simples. Paid Traffic já possui campos cifrados e pode servir como referência técnica. Necessário: configuração por tenant, envelope encryption com versão de chave, rotação, resposta mascarada e redaction de logs.

### 9.3 Uploads

`backend/routes/upload.py` e `upload_optimized.py` gravam em `uploads/<uuid>` sem ownership; `backend/main.py` publica `/uploads` e `/api/uploads` via `StaticFiles`. Necessário namespace `uploads/{tenant_id}/...`, metadados, MIME/hash/tamanho, quota, separação público/privado e rota autorizada ou URL assinada.

### 9.4 Caches, PWA e jobs

- Cache compartilhado somente quando a chave não contém dado tenant e isso for provado.
- Toda chave operacional inclui tenant e versão.
- Troca de empresa/host limpa estado, queries e caches frontend.
- Worker/outbox do Agente WhatsApp e `BackgroundTasks` precisam carregar tenant explicitamente.
- Job sem tenant deve falhar fechado.
- Eventos incluem tenant, job/event ID e correlation ID.
- Service Worker precisa ser testado contra branding/config/mídia residual entre hosts.

## 10. Domínios e resolução de contexto

Regras aprovadas:

- plataforma: tenant do painel vem da autenticação + membership;
- público: hostname normalizado e ativo resolve `tenant_domains.hostname`;
- hostname é globalmente único;
- somente um domínio primário por tenant;
- adicionais redirecionam `301` para o canônico;
- domínio pendente, desabilitado ou desconhecido não carrega dados;
- `X-Forwarded-Host` somente é aceito de proxy confiável;
- DNS A deve apontar para `PLATFORM_PUBLIC_IP`; CNAME somente se configurado;
- SSL só é solicitado depois da validação DNS.

Estados recomendados: `pending`, `dns_invalid`, `dns_verified`, `ssl_pending`, `active`, `failed`, `disabled`.

## 11. Plano de migrations

### Onda 0 — baseline físico

- backup e restore em staging;
- exportar `pg_catalog`: tabelas, colunas, PK/FK/unique/index e sequences;
- registrar row counts e checksums amostrais;
- reconciliar as 196 declarações ORM com tabelas criadas apenas por migration/runtime;
- executar `alembic -c backend/alembic.ini heads`, `current` e `history --verbose`.

### Onda 1 — fundação aditiva

- criar `tenants`, tenant legado UUID e memberships;
- papéis explícitos de plataforma;
- auditoria e contexto;
- nenhuma tabela de negócio recebe `NOT NULL` nesta onda.

### Ondas 2+ — slices de negócio

Ordem: identidade/RBAC → catálogo → clientes → pedidos/itens → pagamentos/webhooks → configurações/operação/frete/cozinha → salão → marketing/CRM/WhatsApp → estoque/CMV/financeiro/fiscal → uploads/jobs/caches.

Para cada slice:

```text
expand nullable sem default
→ backfill idempotente em lotes
→ aplicação dual-compatible
→ índices/uniques/FKs compostas
→ testes A/B e auditoria
→ VALIDATE CONSTRAINT
→ NOT NULL
→ remoção do default legado
```

Não alterar migrations já aplicadas. Criar migrations separadas para expand, backfill e contract.

## 12. Tenant legado e auditoria dos dados

Tenant legado:

- UUID real, slug `legacy`, status `active`;
- preserva todos os IDs, URLs, pedidos, pagamentos, campanhas, credenciais e arquivos atuais;
- `default` é convertido para esse UUID somente por backfill controlado;
- não existe fallback automático para o legado em runtime.

Métricas antes/depois por tabela:

- total;
- NULL em tenant;
- tenants distintos;
- min/max de datas;
- órfãos de FK;
- `child.tenant_id <> parent.tenant_id`;
- duplicatas das futuras uniques;
- somas financeiras e contagens por status.

Gate de integridade: zero NULL, zero órfão novo, zero vínculo cruzado e totais/agregados iguais ao baseline.

## 13. Rollback e deploy progressivo

- Expand é reversível pela aplicação: colunas extras ficam nullable.
- Backfill é idempotente, em lotes e com contagem registrada.
- Rollback de aplicação mantém colunas e dados novos; não executar drop destrutivo.
- Contract só ocorre após backup restaurável, dual compatibility, testes e janela aprovada.
- Reversão de constraint ocorre por migration forward compensatória.
- Corrupção ou mismatch: interromper writes e restaurar snapshot/PITR conforme runbook.

Sequência futura de deploy: banco compatível → backend com flag/dual-read → workers → frontend → canário por tenant/domínio → expansão gradual. Nenhum segundo tenant deve ser ativado antes dos gates do núcleo, auth, webhook e upload.

## 14. Plano de testes

### 14.1 Isolamento A/B

Criar tenants A/B com usuários, produtos, clientes, pedidos, pagamentos, listas, uploads, branding e domínios distintos. Para list/get/create/update/delete:

- A nunca lê ou altera B;
- ID válido de B retorna 404 para A;
- usuário sem membership recebe 403;
- tenant forjado em body/query/header não muda o contexto;
- relações cruzadas são rejeitadas também pelo banco;
- role nula não concede master;
- troca de empresa limpa caches e estado.

### 14.2 Webhook, arquivo, job e cache

- credencial de A com pagamento de B não produz efeito;
- evento duplicado/fora de ordem é idempotente;
- arquivo privado de A não é acessível por B ou anônimo;
- job/evento sem tenant falha;
- retry/restart preserva contexto;
- cache e Service Worker não misturam branding ou mídia.

### 14.3 Regressão

- público: catálogo, carrinho, checkout, pagamentos, webhook, rastreio, conta, fidelidade, cupons, salão e reservas;
- admin: login/refresh/logout, produtos, pedidos/cozinha, uploads, configurações, CRM, marketing, BI, gestão e logística;
- gateways: Pix/cartão Mercado Pago e ASAAS;
- StateMachine permanece o único caminho de mudança de status.

### 14.4 Segurança e performance

Testar IDOR, token/host conflitante, host spoofing, proxy headers, enumeração, escalada, path traversal, MIME/tamanho, segredo em resposta/log, cache poisoning e rate limiting. Medir p50/p95/p99 e erro em staging antes de definir SLO; revisar índices, N+1, backlog e query plans.

## 15. Inventário de arquivos previstos para as próximas fases

Novos componentes esperados, sujeitos à aprovação arquitetural:

```text
backend/models/tenant.py
backend/models/membership.py
backend/models/platform_audit.py
backend/schemas/tenant.py
backend/schemas/membership.py
backend/core/tenant_context.py
backend/dependencies/tenant.py
backend/services/tenant_service.py
backend/services/domain_verification_service.py
backend/routes/platform_tenants.py
backend/routes/tenant_domains.py
backend/migrations/versions/<expand-foundation>.py
backend/migrations/versions/<backfill-slice>.py
backend/migrations/versions/<contract-slice>.py
client/contexts/TenantContext.tsx
client/lib/api.ts
client/App.tsx
client/config/adminNavigation.ts
client/config/adminPageMeta.ts
```

Arquivos existentes de impacto transversal: todos os models tenant-owned, `backend/main.py`, autenticação/RBAC, services/rotas com queries, webhooks, uploads, eventos/jobs/outbox, `client/lib/api.ts`, proteção/layout e experiências públicas.

## 16. Dependências e ambiguidades pendentes

1. Unidade comercial: empresa, marca, loja/unidade ou franquia e suas relações.
2. Se cliente e motoboy podem pertencer a várias empresas.
3. Identidade de consumidor: login global com perfis tenant ou login separado por tenant.
4. Papéis e poderes exatos de `platform_owner`, `platform_admin` e suporte.
5. Planos, preços, limites, trial, tolerância e suspensão.
6. Provider inicial do billing SaaS.
7. Estratégia de criptografia e rotação da chave mestra.
8. `PLATFORM_MAIN_DOMAIN`, `PLATFORM_PUBLIC_IP` e eventual CNAME futuro.
9. Topologia real da VPS, Nginx, TLS, systemd, envs, uploads, backup e observabilidade.
10. Janela, canário e responsáveis pelo primeiro rollout.

Defaults arquiteturais seguros até decisão: uma entidade `tenant` representa a empresa contratante; loja/unidade futura será entidade filha; cliente terá identidade global e perfil/relacionamento tenant; domínio customizado é obrigatório para publicação; billing SaaS não reutiliza pagamentos de pedido.

## 17. Gates da Fase 0 e decisão de avanço

| Gate | Estado | Evidência necessária |
|---|---|---|
| Inventário do código | Aprovado | models, rotas, services, auth, queries e superfícies mapeados |
| Classificação lógica | Aprovado com ressalva | 160 models classificados; 36 models em rotas ainda requerem reconciliação física |
| Estratégia tenant/contexto | Aprovado | fontes confiáveis e fail-closed definidas |
| Plano expand/backfill/contract | Aprovado | ondas, auditoria e rollback definidos |
| Testes A/B e regressão | Aprovado | matriz e critérios definidos |
| Schema PostgreSQL físico | Bloqueado | `pg_catalog`, counts, constraints e Alembic current em cópia |
| Backup/restore | Bloqueado | restore ensaiado e cronometrado |
| Infra VPS/staging | Bloqueado | snapshot de Nginx/systemd/DNS/TLS/envs/uploads |
| Decisões de produto | Bloqueado | itens da seção 16 aprovados |

**Decisão:** a análise de código da Fase 0 está concluída. A Fase 1 não deve começar até fechar os quatro gates bloqueados. Nenhum dado ou contrato foi alterado nesta fase.

## 18. Comandos de validação previstos

Local/documentação:

```powershell
git diff --check -- docs/SAAS_MULTI_TENANT_AUDIT.md
npm.cmd run typecheck
npm.cmd test
npm.cmd run build
```

Staging com Python/PostgreSQL:

```bash
alembic -c backend/alembic.ini heads
alembic -c backend/alembic.ini current
alembic -c backend/alembic.ini history --verbose
pg_dump --format=custom --file=<backup> <database>
pg_restore --list <backup>
```

Os comandos com banco/VPS são instruções; não foram executados no Windows local porque Python/Alembic e a instância PostgreSQL real não estão disponíveis.
