# Central Master da Plataforma Telz

Atualizado em: 2026-08-09

Status desta documentacao: a Central ate `20260816_master_completion` possui
evidencia historica de aplicacao na VPS. O checkout atual acrescenta
`20260817_platform_wave0`, `20260818_platform_operations`, Usuarios,
Configuracoes e os sete modulos operacionais da plataforma. Esse novo conjunto
esta implementado e validado apenas nos gates locais registrados abaixo; ainda
nao ha evidencia de aplicacao na VPS. HTTPS publico, restore ensaiado,
PostgreSQL 15 descartavel e E2E real com dois tenants permanecem gates abertos.

## 1. Objetivo

A Central Master e a superficie administrativa da plataforma SaaS. Ela administra empresas, planos, modulos comerciais, licencas, dominios, cobranca SaaS manual, auditoria e sessoes temporarias de suporte.

O desenho preserva a raiz multiempresa existente:

- `Tenant` continua sendo a entidade de empresa;
- `AdminUser` continua sendo uma identidade administrativa global;
- `TenantMembership` continua representando o vinculo do usuario com a empresa;
- o RBAC de plataforma continua separado do RBAC operacional da empresa;
- pagamentos SaaS nao reutilizam pagamentos de pedidos;
- dominios somente resolvem loja quando estao ativos;
- enforcement operacional continua sendo habilitado gradualmente.

## 2. Status executivo

### Implementado

- schema SaaS aditivo e versionado;
- perfil cadastral 1:1 do tenant;
- planos e catalogo comercial de modulos;
- relacionamento plano-modulo;
- assinatura comercial atual por tenant;
- licenca e historico append-only de eventos;
- overrides de modulo por tenant;
- perfil de cobranca, faturas, itens e pagamentos SaaS manuais;
- metricas de uso e notas internas;
- sessao temporaria de suporte com token opaco one-time, troca por JWT escopado e hash persistido;
- auditoria de plataforma com before/after/reason e redaction de segredos;
- wizard transacional de empresa, owner, perfil, plano, licenca, modulos e dominio opcional;
- dashboard com dados reais;
- listagem server-side com filtros, ordenacao e paginacao;
- detalhe, edicao, suspensao, reativacao e arquivamento de empresa;
- consulta de usuarios, seguranca, uso, notas, modulos, licenca, dominios e invoices;
- verificacao TXT server-side;
- resolver fail-closed somente para dominio e tenant ativos;
- dependency reutilizavel de licenca/modulo no backend;
- teste explicito de isolamento de entitlement entre Tenant A e Tenant B;
- compatibilidade com os endpoints anteriores de tenant.

### Pendente

- validar `20260818_platform_operations` contra PostgreSQL 15 descartavel antes da VPS;
- aplicar `20260817` e `20260818` de forma explicita somente depois desse ensaio;
- ensaiar restauracao dos backups em ambiente descartavel;
- emissao e renovacao automatica de SSL;
- aplicar enforcement de licenca/modulo, rota por rota, nos modulos operacionais legados;
- validar o fluxo visual de suporte ponta a ponta em todas as telas operacionais permitidas;
- autenticacao em duas etapas;
- teste ponta a ponta com PostgreSQL real, DNS real e dois tenants;
- confirmar campos opcionais da interface que ainda nao possuem persistencia canonica.

## 3. Arquitetura

### 3.1 Camadas

- `backend/models/platform_saas.py`: entidades persistidas do dominio SaaS.
- `backend/schemas/platform_master.py`: contratos Pydantic de entrada.
- `backend/services/platform_master_service.py`: casos de uso e transacoes.
- `backend/services/tenant_entitlement_service.py`: politica central de acesso.
- `backend/services/platform_audit_service.py`: auditoria append-only e redaction.
- `backend/services/tenant_domain_service.py`: ciclo de vida e DNS.
- `backend/core/tenant_entitlements.py`: dependencies FastAPI reutilizaveis.
- `backend/routes/platform_tenants.py`: adaptadores HTTP finos.

### 3.2 Fonte de verdade comercial e operacional

`TenantSubscription` define o plano e os termos comerciais atuais. `TenantLicense` e a fonte de verdade para permitir ou bloquear operacoes.

Essa separacao evita duplicar a decisao:

- assinatura responde qual plano foi contratado;
- licenca responde se o tenant pode operar;
- `TenantModule` responde quais modulos estao disponiveis;
- `TenantEntitlementService` combina tenant, licenca, modulo, dependencias, validade e limite.

Alterar o plano:

- encerra a assinatura comercial anterior;
- cria nova assinatura;
- habilita os modulos do novo plano;
- desabilita modulos removidos do plano sem apagar dados;
- preserva adicionais e cortesias conforme a origem do entitlement;
- registra auditoria.

### 3.3 Owner empresarial

O owner criado pelo wizard e diferente do administrador de plataforma que executa o cadastro.

O owner:

- recebe `AdminUser`;
- recebe `TenantMembership(role="owner")`;
- recebe um `Role` tenant-scoped chamado `Owner {slug}`;
- recebe permissoes operacionais tenant-scoped;
- nunca recebe `role_id=None`;
- nao recebe `PlatformRole`;
- nao se torna master global.

### 3.4 Segredos

Respostas publicas usam allowlists. Nao saem pela API:

- `password_hash`;
- `verification_token_hash`;
- `token_hash`;
- Authorization;
- cookies;
- client secrets;
- API keys;
- private keys.

O desafio TXT e mostrado somente quando o dominio e solicitado. O banco preserva apenas o hash usado para comparar os valores observados pelo resolver DNS.

Configuracoes de modulos de integracao sao write-only. `config_json` e
`default_config_json` podem ser gravados, mas as respostas retornam apenas
`config_configured`; o frontend nao le nem reenvia o segredo armazenado. A
auditoria substitui o objeto inteiro por valor redigido. Um modulo ja classificado
como `integrations` tambem nao pode ser movido para um grupo publico, evitando que
uma configuracao antes secreta passe a ser serializada por outra politica.

## 4. Models e tabelas

### 4.1 Raiz existente reaproveitada

- `Tenant` / `tenants`
- `AdminUser` / `admin_users`
- `TenantMembership` / `tenant_memberships`
- `PlatformRole`
- `PlatformPermission`
- `PlatformUserRole`
- `Role`
- `RbacModule`
- `RbacPermission`
- `RolePermission`
- `TenantDomain`
- `PlatformAuditLog`

### 4.2 Novos models

| Model | Tabela | Responsabilidade |
|---|---|---|
| `TenantProfile` | `tenant_profiles` | Perfil cadastral 1:1 |
| `SaaSPlan` | `saas_plans` | Plano comercial |
| `SaaSModule` | `saas_modules` | Catalogo comercial de modulos |
| `SaaSPlanModule` | `saas_plan_modules` | Modulos incluidos no plano |
| `TenantSubscription` | `tenant_subscriptions` | Plano/termos atuais do tenant |
| `TenantLicense` | `tenant_licenses` | Estado operacional da licenca |
| `TenantLicenseEvent` | `tenant_license_events` | Historico da licenca |
| `TenantModule` | `tenant_modules` | Entitlement por tenant |
| `TenantBillingProfile` | `tenant_billing_profiles` | Dados de cobranca SaaS |
| `SaaSInvoice` | `saas_invoices` | Fatura SaaS |
| `SaaSInvoiceItem` | `saas_invoice_items` | Itens calculados da fatura |
| `SaaSPayment` | `saas_payments` | Pagamento SaaS manual |
| `SupportSession` | `support_sessions` | Sessao temporaria de suporte |
| `TenantInvitation` | `tenant_invitations` | Convite one-time para membership |
| `TenantUsageMetric` | `tenant_usage_metrics` | Uso por periodo |
| `TenantInternalNote` | `tenant_internal_notes` | Notas internas |

Valores monetarios usam `Numeric(18,2)` e `Decimal`. Constraints impedem valores negativos, quantidade invalida e periodo de fatura invertido. Totais sao calculados no backend.

### 4.3 Dominio ampliado

Estados:

- `pending`;
- `awaiting_dns`;
- `verifying`;
- `verified`;
- `active`;
- `dns_error`;
- `ssl_error`;
- `suspended`;
- `removed`.

Campos novos:

- `is_primary`;
- `expected_txt_record`;
- `expected_cname`;
- `suspended_at`;
- `removed_at`;
- `last_checked_at`;
- `ssl_status`;
- `ssl_issued_at`;
- `ssl_expires_at`;
- `error_message`.

Somente um dominio ativo pode ser principal por tenant.

### 4.4 Auditoria ampliada

Campos novos:

- `actor_type`;
- `before_data`;
- `after_data`;
- `reason`.

Referencias de historico usam `SET NULL` quando o ator ou recurso removivel deixa de existir. Services nao implementam delete fisico de historico.

## 5. API

Todos os endpoints abaixo sao registrados com prefixo `/api`.

### 5.1 Dashboard e catalogos

- `GET /admin/platform/dashboard`
- `GET /admin/platform/plans`
- `POST /admin/platform/plans`
- `PATCH /admin/platform/plans/{plan_id}`
- `GET /admin/platform/modules`
- `POST /admin/platform/modules/seed`
- `POST /admin/platform/modules`
- `PATCH /admin/platform/modules/{module_id}`
- `GET /admin/platform/audit-logs`

Dashboard entrega os grupos `tenants`, `licenses`, `billing`, `domains`, `generated_at` e aliases `metrics`/`alerts`.

### 5.2 Empresas

- `GET /admin/platform/tenants`
- `POST /admin/platform/tenants`
- `GET /admin/platform/tenants/{tenant_id}`
- `PATCH /admin/platform/tenants/{tenant_id}`
- `PATCH /admin/platform/tenants/{tenant_id}/status`
- `POST /admin/platform/tenants/{tenant_id}/suspend`
- `POST /admin/platform/tenants/{tenant_id}/reactivate`
- `POST /admin/platform/tenants/{tenant_id}/archive`

Compatibilidade:

- `GET` sem `page` preserva o array legado;
- `GET` com `page` retorna `{items,total,page,page_size,pages}`;
- `POST` aceita o payload simples legado ou o wizard transacional.

Wizard:

- tenant;
- owner;
- profile no nivel superior;
- `plan_id`;
- `module_ids`;
- `trial_days`;
- dominio opcional.

### 5.3 Contexto da empresa

- `GET /admin/platform/tenants/{tenant_id}/users`
- `POST /admin/platform/tenants/{tenant_id}/users`
- `PATCH /admin/platform/tenants/{tenant_id}/users/{user_id}/role`
- `PATCH /admin/platform/tenants/{tenant_id}/users/{user_id}/status`
- `POST /admin/platform/tenants/{tenant_id}/users/{user_id}/block`
- `POST /admin/platform/tenants/{tenant_id}/users/{user_id}/reactivate`
- `POST /admin/platform/tenants/{tenant_id}/users/{user_id}/reset-password`
- `POST /admin/platform/tenants/{tenant_id}/users/{user_id}/revoke-sessions`
- `POST /admin/platform/tenants/{tenant_id}/transfer-ownership`
- `GET /admin/platform/tenants/{tenant_id}/invitations`
- `POST /admin/platform/tenants/{tenant_id}/invitations`
- `POST /admin/platform/tenants/{tenant_id}/invitations/{invitation_id}/resend`
- `POST /admin/platform/invitations/accept`
- `GET /admin/platform/tenants/{tenant_id}/security`
- `GET /admin/platform/tenants/{tenant_id}/usage`
- `POST /admin/platform/tenants/{tenant_id}/usage/refresh`
- `GET /admin/platform/tenants/{tenant_id}/notes`
- `POST /admin/platform/tenants/{tenant_id}/notes`
- `GET /admin/platform/tenants/{tenant_id}/modules`
- `PUT /admin/platform/tenants/{tenant_id}/modules`
- `PUT /admin/platform/tenants/{tenant_id}/plan`
- `GET /admin/platform/tenants/{tenant_id}/license`
- `POST /admin/platform/tenants/{tenant_id}/license/{action}`

Acoes de licenca implementadas:

- `renew`;
- `extend`;
- `start_trial`;
- `convert`;
- `courtesy`;
- `grace` / `grace_period`;
- `expire`;
- `cancel`;
- `suspend`;
- `block`;
- `reactivate`.

### 5.4 Dominios

- `GET /admin/platform/domains`
- `GET /admin/platform/tenants/{tenant_id}/domains`
- `POST /admin/platform/tenants/{tenant_id}/domains`
- `POST /admin/platform/domains/{domain_id}/verify`
- `POST /admin/platform/domains/{domain_id}/activate`
- `POST /admin/platform/domains/{domain_id}/primary`
- `POST /admin/platform/domains/{domain_id}/suspend`
- `DELETE /admin/platform/domains/{domain_id}`
- `GET /runtime/host-surface`

O frontend nao envia `verified=true`. O backend consulta o TXT esperado e compara a prova observada com o hash persistido.

### 5.5 Billing SaaS

- `GET /admin/platform/tenants/{tenant_id}/invoices`
- `POST /admin/platform/tenants/{tenant_id}/invoices`
- `POST /admin/platform/invoices/{invoice_id}/payments`
- `POST /admin/platform/invoices/{invoice_id}/discount`
- `POST /admin/platform/invoices/{invoice_id}/courtesy`
- `POST /admin/platform/invoices/{invoice_id}/extend`
- `POST /admin/platform/invoices/{invoice_id}/cancel`
- `GET /admin/platform/invoices/{invoice_id}/history`

Esta API nao usa `payments`, `payment_events` ou `payment_gateway_config` de pedidos.

### 5.6 Suporte

- `POST /admin/platform/support-sessions`
- `POST /admin/platform/support-sessions/exchange`
- `POST /admin/platform/support-sessions/{session_id}/end`

A sessao possui motivo, prazo de 5 a 120 minutos, ator, tenant, usuario alvo opcional, IP, user-agent e auditoria.

Implementado: emissao do token opaco temporario, persistencia apenas do hash,
consumo one-time, JWT assinado limitado ao tenant e prazo da sessao, verificacao
da sessao ativa em cada request e encerramento auditado. O JWT de suporte e
negado na Central Master, RBAC, usuarios globais e superficies de segredo, como
QR/pairing do WhatsApp Gateway.

O allowlist backend e fail-closed: alem de `/admin/auth/me`, o JWT de suporte
somente alcanca `/gestao/finance` e `/store-operation`, que usam contexto de
tenant validado. Pedidos, pagamentos de pedidos, produtos, delivery, salao,
fiscal, estoque, WhatsApp Gateway e o prefixo amplo `/gestao` permanecem
negados ate haver prova de ownership em todas as rotas dependentes.

Pendente: validacao E2E do banner e de cada tela operacional permitida em ambiente executavel.

## 6. Permissoes

- `tenants.view`: consultas de empresas e catalogos.
- `tenants.manage`: mutacoes de tenant, planos, modulos, dominios e billing manual.
- `audit.view`: consulta de auditoria.
- `support.impersonate`: inicio e encerramento de suporte.

`PLATFORM_RBAC_ENABLED=false` esconde essas APIs com 404. Nenhuma permissao de plataforma e inferida de `role_id=None`.

## 7. Flags

Necessarias para a superficie Master existente:

```env
PLATFORM_RBAC_ENABLED=true
MULTI_TENANT_AUTH_ENABLED=true
TENANT_DOMAINS_ENABLED=true
TENANT_DOMAINS_PLATFORM_HOSTNAMES=erp.telz.com.br
```

Relacionadas ao proxy:

```env
TENANT_DOMAINS_TRUST_PROXY_HEADERS=true
TENANT_DOMAINS_TRUSTED_PROXY_IPS=<CIDRs-ou-IPs-do-proxy>
```

Continuam graduais e desligadas por padrao:

```env
TENANT_IDENTITY_CATALOG_ENFORCEMENT_ENABLED=false
TENANT_CUSTOMERS_ORDERS_ENFORCEMENT_ENABLED=false
MULTI_TENANT_WAVE6_ORM_ENABLED=false
TENANT_OPERATIONS_ENFORCEMENT_ENABLED=false
TENANT_PAYMENT_WEBHOOKS_ENABLED=false
TENANT_BACKGROUND_CONTEXT_ENABLED=false
TENANT_UPLOAD_NAMESPACE_ENABLED=false
TENANT_CREDENTIALS_ENABLED=false
```

Nao habilitar todas as flags simultaneamente. Schema tenantizado nao comprova que todas as consultas antigas estao isoladas.

## 8. Revisions Alembic

### `20260814_merge_all_heads`

Bridge linear sem DDL, filha direta de `20260813_automation_event_core`. O nome
historico da revision foi mantido por compatibilidade de identificador, mas ela
nao e mais uma merge revision.

### `20260815_master_central_core`

Cria as tabelas SaaS e amplia dominio/auditoria.

Antes da fundacao da Onda 0, o grafo estatico do checkout apresentava um unico
head:

```text
20260816_master_completion
```

Isso nao substitui a verificacao do banco real.

### `20260816_master_completion`

Completa contratos e campos de usuarios/licencas/convites e torna `roles`,
`role_permissions`, `user_permissions` e `admin_audit_logs` estritamente
tenant-scoped. A revision remove a unicidade global legada `roles_name_key` e
mantem a unicidade por tenant. O startup legado continua criando tabelas
historicas com `create_all`, mas exclui
explicitamente todas as tabelas pertencentes a `20260815`/`20260816`; por isso,
as migrations da Central devem ser aplicadas antes do restart da API.

### `20260817_platform_wave0`

Filha direta de `20260816_master_completion`. Semeia somente o catalogo de
permissoes futuras da Central e os grants de menor privilegio para
`platform_owner`, `platform_admin` e `platform_support`. A migration nao publica
endpoints nem executa acoes operacionais; as superficies HTTP sao entregues
pelo codigo da aplicacao nas etapas seguintes.

Antes da fundacao operacional persistida, o head estatico era:

```text
20260817_platform_wave0
```

### `20260818_platform_operations`

Filha direta de `20260817_platform_wave0`. Cria apenas dados operacionais
redigidos da Central:

- `platform_error_events`, com agregacao por fingerprint, estados auditaveis e
  sem traceback, corpo de request ou credenciais;
- `platform_worker_heartbeats`, com liveness duravel por worker/instancia.

O upgrade e o downgrade declaram simetricamente os indices. Os models pertencem
exclusivamente ao Alembic e ficam fora do `create_all` legado. O head unico do
checkout atual e:

```text
20260818_platform_operations
```

O banco da VPS permanece comprovado somente em `20260816_master_completion`
ate as duas novas revisions passarem pelos gates e serem aplicadas.

## 9. Validacao registrada

Executado:

- `git diff --check`;
- import completo da aplicacao: `APP IMPORT OK 1447`;
- suite Python completa: `140 passed`, com um warning Pydantic preexistente;
- `alembic heads`: `20260816_master_completion (head)`;
- `alembic history` da cadeia `20260813` ate `20260816`;
- geracao SQL offline das tres revisions da Central;
- verificacao estatica das dependencies de permissao em cada rota;
- busca por serializacao de hashes;
- busca por `Float` em valores monetarios.

Adicionado:

- teste Tenant A/Tenant B para entitlement;
- teste de licenca expirada;
- teste de serializers sem hashes;
- teste de redaction;
- teste de permissoes explicitas nas rotas.

Nao executado localmente:

- PostgreSQL real;
- `alembic current`, porque nao ha PostgreSQL local ouvindo em `localhost:5432`;
- aplicacao/downgrade das migrations em banco descartavel;
- DNS real.

O runtime Python 3.12 embarcado, combinado com as dependencias locais da
aplicacao, permitiu executar import, pytest e Alembic CLI. Isso nao substitui o
ensaio em PostgreSQL 15 nem comprova o estado do banco da VPS.

Validado na VPS em 2026-08-02 para o commit `2f10068` e a revision
`20260816_master_completion`:

- backup PostgreSQL validado com `pg_restore --list`;
- backup do runtime Baileys validado com leitura silenciosa do arquivo tar;
- migrations `20260814`, `20260815` e `20260816` aplicadas explicitamente;
- `alembic current` e `alembic heads` convergentes em `20260816_master_completion`;
- dependencias Python consistentes com `pip check`;
- typecheck, 13 arquivos/51 testes frontend e build aprovados;
- `telz-api`, `telz-web` e `telz-whatsapp-gateway` ativos;
- Nginx valido e health check interno aprovado.

Essa verificacao nao comprova HTTPS publico, restore, fluxo visual E2E, DNS
real de tenant nem isolamento ponta a ponta entre dois tenants.

## 10. Campos nao persistidos ou nao completos

Nao declarar como persistidos:

- porte da empresa;
- 2FA;
- status real de emissao SSL sem integracao de infraestrutura;
- aliases de formulario como `document`, `institutional_email`, `street` e `district`.

Campos canonicos persistidos no perfil:

- `tax_id`;
- `email`;
- `address_line`;
- `neighborhood`;
- demais campos declarados em `TenantProfile`.

Se a interface usar aliases, deve converte-los para os nomes canonicos antes do request. Campos extras nao devem ser silenciosamente tratados como gravados.

## 11. Deploy seguro

Nao executar `alembic upgrade head` cegamente.

### 11.1 Preflight

1. Confirmar checkout e revision publicada.
2. Fazer backup do PostgreSQL.
3. Preservar `backend/.env`, uploads, certificados e `.runtime/baileys`.
4. Ativar a `.venv` da aplicacao.
5. Executar:

```bash
alembic -c backend/alembic.ini heads
alembic -c backend/alembic.ini current
alembic -c backend/alembic.ini history
```

6. Confirmar a cadeia linear `20260813 -> 20260814 -> 20260815 -> 20260816 -> 20260817_platform_wave0 -> 20260818_platform_operations` no ambiente.
7. Se `current` nao pertencer a essa cadeia, interromper o deploy e reconciliar a topologia. Nao marcar revisions manualmente sem auditoria.
8. Instalar dependencias Python alteradas.
9. Rodar pytest e teste de migration em banco descartavel.

### 11.2 Aplicacao explicita

Somente depois do preflight:

```bash
alembic -c backend/alembic.ini upgrade 20260814_merge_all_heads
alembic -c backend/alembic.ini upgrade 20260815_master_central_core
alembic -c backend/alembic.ini upgrade 20260816_master_completion
alembic -c backend/alembic.ini upgrade 20260817_platform_wave0
alembic -c backend/alembic.ini upgrade 20260818_platform_operations
```

Depois:

1. instalar as dependencias da revisao e executar o build frontend;
2. reiniciar `telz-api` e `telz-web` conforme as units instaladas;
3. validar `/health` e o status dos dois services;
4. validar logs;
5. consultar `current` novamente;
6. testar login de plataforma e troca obrigatoria de senha;
7. testar dashboard;
8. criar tenant descartavel com owner separado;
9. testar Tenant A versus Tenant B;
10. testar solicitacao DNS sem ativar SSL automaticamente.

## 12. Rollback

### 12.1 Antes de dados reais

Se a migration foi aplicada em ambiente descartavel e ainda nao existem dados SaaS:

```bash
alembic -c backend/alembic.ini downgrade 20260814_merge_all_heads
```

Esse downgrade remove as tabelas da Central Master e normaliza estados novos de dominio antes de restaurar o check antigo. Ele e destrutivo.

### 12.2 Depois de dados reais

Nao executar downgrade destrutivo.

Preferir:

1. colocar a superficie Master em manutencao;
2. restaurar o codigo compativel ou aplicar hotfix forward-only;
3. preservar tabelas e historicos;
4. restaurar backup somente com janela e aprovacao operacional;
5. comparar `current`, logs e integridade antes de liberar trafego.

`20260814_merge_all_heads` e uma bridge linear sem DDL. Seu downgrade apenas
retorna o ponteiro para `20260813_automation_event_core`.

## 13. Checklist de liberacao

- [ ] backup criado e restauracao ensaiada;
- [ ] cadeia linear `20260813 -> 20260818_platform_operations` confirmada no ambiente real;
- [ ] `current` e `history` registrados;
- [ ] Python imports e pytest aprovados;
- [ ] migration testada em PostgreSQL descartavel;
- [ ] API sem exposicao de hashes;
- [ ] owner sem autoridade de plataforma;
- [ ] Tenant A nao acessa Tenant B;
- [ ] empresa bloqueada nao executa operacao protegida;
- [ ] billing e suporte continuam acessiveis para regularizacao;
- [ ] dominio pendente nao resolve loja;
- [ ] SSL marcado como pendente quando nao emitido;
- [ ] enforcement legado ativado somente por modulo validado.

## 14. Addendum da segunda rodada - 2026-07-29

Este addendum registra o estado final da segunda rodada de correcoes. Ele e
aditivo e nao substitui os riscos, o preflight ou o checklist anteriores.

### 14.1 Dashboard e empresas

O dashboard passou a calcular dados reais a partir das tabelas da plataforma:

- total de tenants e tenants ativos;
- tenants criados no mes;
- total de usuarios;
- licencas em trial e ativas;
- MRR normalizado pelo ciclo dos planos ativos;
- faturas vencidas;
- dominios ativos.

Os alertas agora sao uma lista tipada e identificam tenants sem owner, sem
plano, sem dominio, com licenca vencendo em ate sete dias ou com fatura
vencida. A listagem de empresas ganhou filtros por tenant, email do owner,
plano, dominio, status financeiro, modulo e proximidade do vencimento, com
ordenacao limitada a campos permitidos.

### 14.2 Usuarios do tenant

A superficie Master passou a oferecer criacao de usuario, alteracao de papel,
alteracao de status, bloqueio, reativacao, redefinicao de senha e transferencia
de ownership. O backend valida o limite de usuarios do plano, impede papel
global de plataforma e preserva exatamente um owner durante a transferencia.

O campo `force_password_change` e persistido, retornado no login e aplicado no
backend: enquanto ativo, somente o perfil e a troca de senha autenticada ficam
disponiveis. A troca ou redefinicao de senha incrementa `auth_version`, e a acao
auditada de revogar sessoes invalida JWTs anteriores sem bloquear tokens antigos
enquanto nenhuma revogacao explicita tiver ocorrido.

### 14.3 Billing

O registro manual de pagamento:

- bloqueia a fatura com `FOR UPDATE`;
- impede pagamento acima do saldo;
- protege os estados finais `paid`, `cancelled`, `refunded` e `courtesy`;
- usa referencia unica por tenant quando informada;
- registra auditoria para inclusao e replay;
- trata disputa do indice unico.

O replay por referencia e validado antes do bloqueio por estado final. Assim,
uma repeticao com a mesma referencia, fatura e valor retorna a resposta
idempotente mesmo depois de a fatura estar `paid`; reutilizacao da referencia
com fatura ou valor diferente retorna conflito.

### 14.4 Enforcement operacional

Foi adicionada a flag explicita:

```env
TENANT_ENTITLEMENT_ENFORCEMENT_ENABLED=false
```

Ela permanece desativada por padrao. Quando ativada, o enforcement operacional
consulta o tenant da sessao e valida licenca e modulo antes das escritas
protegidas. Nesta rodada a integracao foi aplicada somente a operacoes de
escrita de pedidos e pagamentos.

Essa cobertura e parcial. As demais rotas legadas ainda precisam ser
classificadas e protegidas gradualmente antes de a flag ser habilitada em
producao.

### 14.5 Testes adicionados

Foram adicionados ou ampliados testes para:

- isolamento de entitlement entre Tenant A e Tenant B;
- comportamento da flag desligada e ligada;
- lock, estado final, referencia unica e auditoria de billing;
- ordem do replay idempotente antes do gate de estado final;
- limite de usuarios e transferencia de owner;
- contrato tipado de dashboard;
- permissoes das novas rotas;
- erros de dominio no ciclo de dominios.
- escopo, consumo one-time, expiracao e isolamento `X-Tenant-ID` do suporte;
- troca obrigatoria de senha, `auth_version` e claim malformada fail-closed;
- convites para identidade existente, cross-tenant e expirados;
- cobranca paga/cortesia zero e preco efetivo por ciclo/contrato;
- contratos de resposta em todas as rotas e grafo estatico da revision 20260816.

Os arquivos principais sao `tests/test_platform_master_completion.py`,
`tests/test_platform_master_security.py` e `tests/test_platform_master_contracts.py`.
Em 2026-08-01, o conjunto direcionado de Master, rotas, dominios, autenticacao,
RBAC e startup concluiu com `57 passed`, sem falhas. A suite Python completa
concluiu com `140 passed`. Permaneceu um warning de deprecacao Pydantic
preexistente.

### 14.6 Fechamento de seguranca e consistencia - 2026-07-31

- owners ativos passam a administrar usuarios e RBAC somente no tenant da
  membership; papel de plataforma sem membership ativa nao concede esse acesso;
- owner nao pode ser demovido, desativado ou removido pelo CRUD generico; a
  mudanca exige transferencia de propriedade;
- identidades com qualquer membership externa nao revogada nao podem sofrer
  mutacao global de senha, e-mail, papel ou status pelo tenant atual;
- troca e reset de senha incrementam `auth_version`, rejeitam reutilizacao e
  aplicam o limite bcrypt de 72 bytes;
- a listagem de empresas entrega documento, nome fantasia, responsavel, ultimo
  acesso, dias restantes e status de dominio com valores reais ou `null`;
- faturas `pending` vencidas transitam uma unica vez para `overdue` antes do
  dashboard, listagem de empresas e listagem de faturas, com auditoria de sistema;
- busca global de dominios cobre hostname, nome e slug do tenant por `JOIN`;
- verificacao, ativacao, definicao de principal, suspensao e remocao de dominio
  ficam no service; remocao exige motivo e todas as acoes permanecem auditadas;
- alteracao de status de plano exige motivo de auditoria.

### 14.7 Pendencias confirmadas

- `TENANT_ENTITLEMENT_ENFORCEMENT_ENABLED` continua `false` por padrao;
- enforcement cobre apenas parte das escritas de pedidos e pagamentos;
- suporte, revogacao e contratos Pydantic estao implementados no backend, mas o
  fluxo E2E ainda precisa ser exercitado em runtime real;
- `alembic current` e a aplicacao ate `20260816` foram confirmados na VPS;
  `20260817_platform_wave0`, `20260818_platform_operations`, restore e fluxo
  ponta a ponta ainda precisam dos gates descritos antes da proxima publicacao.

## 15. Onda 0 - fundacao operacional

Esta onda prepara autorizacao, backup e observabilidade e entrega localmente
Usuarios, Configuracoes e os modulos operacionais descritos na secao 17.

### 15.1 Permissoes futuras

Catalogo semeado por `20260817_platform_wave0`:

- `platform_users.view` / `platform_users.manage`;
- `platform_settings.view` / `platform_settings.manage`;
- `monitoring.view`;
- `integrations.view` / `integrations.manage`;
- `jobs.view` / `jobs.manage`;
- `gateway.view` / `gateway.manage`;
- `errors.view` / `errors.manage`;
- `storage.view`;
- `backups.view`.

Matriz inicial de menor privilegio:

| Role | Grants da Onda 0 |
|---|---|
| `platform_owner` | Todas as permissoes acima |
| `platform_admin` | Todas, exceto `platform_users.manage` e `platform_settings.manage` |
| `platform_support` | Somente `monitoring.view`, `integrations.view`, `jobs.view`, `gateway.view` e `errors.view` |

Nao existem `storage.manage` nem `backups.manage` nesta onda. Operacoes
destrutivas continuam fora da aplicacao.

`platform_users.view` ja protege o novo endpoint paginado
`GET /api/admin/platform/users` e a pagina `/painel/usuarios-plataforma`. O
recorte permite busca e filtro por role, usa respostas allowlisted e nao publica
POST, PATCH, PUT ou DELETE. `platform_users.manage` fica reservado para uma
onda posterior e nao concede mutacao nesta entrega.

### 15.2 Backup fortalecido

`scripts/backup-telz.sh` passa a:

- usar `umask 077`;
- validar o dump PostgreSQL com `pg_restore --list`;
- validar silenciosamente os arquivos tar de uploads e do runtime
  `.runtime/baileys`, quando esses diretorios existem;
- comparar silenciosamente a copia protegida de `backend/.env`;
- nao listar conteudo de arquivos nem valores de segredo no output.

O backup incluir o runtime Baileys nao comprova restauracao. O restore continua
manual, destrutivo e condicionado a janela operacional aprovada.

### 15.3 Gates antes de aplicar o checkout operacional

- [x] testes direcionados de migrations, contratos e superficies operacionais aprovados localmente;
- [x] `alembic heads` retorna somente `20260818_platform_operations` no checkout;
- [ ] upgrade ensaiado em PostgreSQL 15 descartavel;
- [ ] backup novo criado e todos os artefatos validados na VPS;
- [ ] restore ensaiado fora de producao;
- [ ] HTTPS publico validado;
- [ ] E2E da Central e isolamento Tenant A/Tenant B validados.

## 16. Configuracoes da plataforma - recorte read-only

O segundo recorte funcional remove a indisponibilidade de Configuracoes da
plataforma sem transformar a Central em editor de ambiente. A superficie usa:

- endpoint `GET /api/admin/platform/settings`;
- pagina `/painel/configuracoes-plataforma`, separada de
  `/painel/configuracoes`, que pertence ao painel operacional do tenant;
- permissao `platform_settings.view`, sem reutilizar permissoes tenant-scoped;
- resposta `PlatformSettingsOut` dentro do envelope padrao da API.

A permissao depende de `20260817_platform_wave0`. `platform_owner` e
`platform_admin` possuem leitura; `platform_support` nao recebe essa permissao.
`platform_settings.manage` permanece reservado e nao publica qualquer operacao
de escrita nesta entrega.

### 16.1 Allowlist de resposta

O endpoint nao serializa `Settings`, arquivos `.env` nem configuracoes da loja.
A resposta e montada por allowlist e possui somente os grupos:

- `source`: identificacao estatica da origem de configuracao, sem caminho de
  arquivo;
- `read_only`: sempre `true` neste recorte;
- `restart_required`: informa que uma futura alteracao operacional somente
  produziria efeito por procedimento de deploy/restart, sem executar esse
  procedimento;
- `status`: resumo derivado do backend;
- `application`: identidade e versao publicas da aplicacao e estado de debug;
- `security`: estado do segredo JWT como `configured`, `default` ou `missing` e
  apenas os booleanos allowlisted de autenticacao e RBAC;
- `domains`: hostnames de plataforma normalizados, contagens de entradas
  validas/invalidas e somente a quantidade de proxies confiaveis;
- `rollout_flags`: somente flags booleanas explicitamente declaradas no service
  e validadas pelo schema;
- `alerts`: lista tipada de alertas seguros.

Essa allowlist nunca inclui `DATABASE_URL`, segredo JWT, senhas, tokens, chaves
de API, cookies, headers de autorizacao, conteudo integral de `.env`, IPs ou
valores da lista de proxies confiaveis. Tambem nao reutiliza `site_config`, que
continua pertencendo a configuracao da loja e nao representa estado global da
plataforma.

### 16.2 Alertas seguros

Cada alerta retorna somente `key`, `severity`, `title` e `description`. O backend
deriva alertas para estados operacionais inseguros ou incompletos sem interpolar
o valor que causou o alerta. Assim, a pagina pode sinalizar segredo JWT padrao
ou ausente, debug ativo e inconsistencias de dominio/proxy sem revelar
credenciais, enderecos privados ou configuracao bruta. Se o RBAC estiver
desabilitado, a dependencia de autorizacao encerra a requisicao com `404` antes
da resposta; o alerta correspondente permanece uma defesa do service, nao um
estado visivel pela pagina nessa condicao fail-closed.

Os alertas sao informativos. Nao existe acao de corrigir, salvar, reiniciar,
recarregar processo ou editar variavel de ambiente na API ou na interface.

### 16.3 Limites e gates operacionais

Este recorte:

- publica somente `GET`; nao adiciona `POST`, `PUT`, `PATCH` ou `DELETE`;
- nao cria tabela nem migration adicional;
- nao grava em `.env`, `site_config`, banco ou filesystem;
- nao reinicia API, frontend, gateway, worker ou Nginx;
- nao afirma que uma flag exibida ja foi validada ponta a ponta.

A publicacao continua condicionada aos gates da secao 15.3. Em especial,
`20260818_platform_operations` ainda precisa ser ensaiada em PostgreSQL 15
descartavel e aplicada explicitamente na VPS; HTTPS publico, restore fora de
producao e E2E real com dois tenants continuam pendentes e nao sao comprovados
pela tela de Configuracoes.

## 17. Modulos operacionais da plataforma

O checkout atual remove o estado `INDISPONIVEL` dos sete modulos restantes da
Central e preserva menor privilegio. Toda resposta usa schema Pydantic e
envelope da API; as rotas nao executam `sudo`, `systemctl` ou subprocessos.

### 17.1 Superficies entregues

| Modulo | API base | Permissao | Mutacao |
|---|---|---|---|
| Saude dos servicos | `/api/admin/platform/health` | `monitoring.view` | nenhuma |
| Integracoes | `/api/admin/platform/integrations` | `integrations.view` | nenhuma |
| Filas e jobs | `/api/admin/platform/jobs` | `jobs.view` | nenhuma |
| WhatsApp Gateway | `/api/admin/platform/gateway` | `gateway.view` | nenhuma |
| Erros | `/api/admin/platform/errors` | `errors.view` | reconhecer/resolver exige `errors.manage` |
| Armazenamento | `/api/admin/platform/storage` | `storage.view` | nenhuma |
| Backups | `/api/admin/platform/backups` | `backups.view` | nenhuma |

`GET /api/admin/platform/session` retorna somente roles e permissoes da sessao
para o frontend filtrar navegacao e bloquear acesso sem capacidade. O backend
continua sendo a autoridade; esconder um item de menu nao concede nem revoga
permissao.

### 17.2 Observabilidade segura

O coletor root-owned grava snapshots sanitizados em
`PLATFORM_MONITORING_SNAPSHOT_DIR`, cujo default e
`/var/lib/telz/monitoring`. A API aceita somente arquivos regulares, dentro do
diretorio permitido, com tamanho limitado e freshness explicita. Snapshot
ausente, invalido ou antigo produz `unknown`/`stale`; nunca um falso estado
saudavel.

Health, storage, Gateway e backup consomem somente snapshots sanitizados.
Integracoes consultam estado allowlisted sem selecionar credenciais. A frota do
Gateway projeta no SQL apenas os quatro ultimos digitos do telefone e retorna o
valor mascarado. Backups expoem metadados de execucao e componentes, nunca
`environment.env`, dump, archive, checksum bruto ou caminho privado.

### 17.3 Validacao local e limites

Em 2026-08-09, os testes focais de Master, Onda 0, sessao e operacoes
concluiram com `41 passed`, e a suite backend completa concluiu com
`176 passed`. Typecheck, Vitest (`20` arquivos, `99` testes), build completo e
`bash -n` nos `22` scripts do instalador/operacao
tambem passaram. `git diff --check` passou e `alembic heads` retornou um unico
`20260818_platform_operations`. Permaneceu um warning Pydantic preexistente.

Esses resultados nao comprovam:

- upgrade/downgrade em PostgreSQL 15 real;
- workflow CI publicado;
- aplicacao na VPS;
- snapshots gerados pelo timer sob systemd;
- HTTPS publico;
- restore em ambiente descartavel;
- E2E de navegador e isolamento real entre dois tenants.
