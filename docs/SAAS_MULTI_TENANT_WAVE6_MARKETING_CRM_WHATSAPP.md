# Onda 6 — Marketing, CRM, WhatsApp, Tráfego e BI

## Escopo comprovado

Esta onda foi inventariada a partir dos models em `backend/models` e dos models ORM
declarados localmente nas rotas `ads_oauth.py`, `automations.py`, `crm.py`,
`email_marketing.py`, `exit_popup.py`, `marketing.py` e `whatsapp_marketing.py`.

Foram incluídos somente dados operacionais pertencentes à empresa:

- CRM, perfis/sugestões/jobs de IA e histórico do cliente;
- campanhas, automações, visitantes, tracking, Email e WhatsApp Marketing;
- tráfego pago, contas/campanhas Ads, pixels, OAuth state e métricas;
- BI e inteligência de marketing;
- chatbot, Agente WhatsApp, outbox/jobs e WhatsApp Gateway.

Catálogos de plataforma, identidade administrativa, papéis globais e billing SaaS
permanecem fora. `admin_users` continua global nesta onda; por isso referências de
auditoria/operador para essa tabela não recebem FK composta.

## Migrations

### `20260801_tenant_marketing_crm_whatsapp_expand`

- encadeada após `20260731_tenant_operations_backfill`;
- adiciona `tenant_id` nullable e sem default nas tabelas ainda não tenantizadas;
- remove o server default das colunas legadas, mantendo-as nullable na fase expand;
- adiciona FK para `tenants` com `NOT VALID` e unique `(tenant_id, id)` em cada tabela;
- adiciona índices unique tenant-scoped para chaves comprovadas e singletons;
- adiciona FKs compostas `(tenant_id, foreign_id)` com `NOT VALID`;
- não aplica `NOT NULL`, não valida constraints e não remove uniques globais legadas.

As FKs compostas cujo relacionamento escalar usa `ON DELETE SET NULL` ficam como
`NO ACTION`. Um `SET NULL` composto apagaria também `tenant_id`; a FK escalar
existente continua responsável por limpar apenas a coluna de relacionamento. FKs
de filhos descartáveis preservam `ON DELETE CASCADE`.

### `20260802_tenant_marketing_crm_whatsapp_backfill`

- exige que `tenant-legacy-default` exista e esteja ativo;
- rejeita todo rótulo de tenant desconhecido antes de escrever;
- verifica duplicidades das chaves tenant-scoped e dos singletons;
- verifica todas as relações destinadas às FKs compostas e aborta em mismatch;
- converte explicitamente `NULL` e `tenant_id='default'` para o tenant legado;
- normaliza também o campo de compatibilidade `company_id='default'` das tabelas
  do WhatsApp Gateway/delivery, após preflight de valores desconhecidos;
- downgrade é intencionalmente não destrutivo.

## Compatibilidade e riscos

- Models e queries ainda podem usar o rótulo legado até a onda de aplicação; a
  migration remove apenas default no schema, sem contract prematuro.
- Uniques globais permanecem vigentes durante dual compatibility e só podem ser
  removidos em uma futura migration contract, depois do canário multiempresa.
- Credenciais continuam nos campos atuais. Tenantizar ownership não substitui a
  futura criptografia/rotação/redaction dos segredos.
- Jobs, outbox, webhooks e queries ainda precisam propagar o contexto na aplicação;
  esta onda garante somente o caminho de dados compatível.
- `ads_oauth_states` é tenant-owned: estado OAuth sem tenant não pode ser usado
  como autoridade quando a integração da aplicação for habilitada.

## Alinhamento ORM da fase expand

Os 83 models, inclusive os declarados localmente em rotas, agora expõem
`tenant_id` nullable, sem default Python ou server default. O helper
`backend/core/wave6_tenant_orm.py` registra no metadata os mesmos nomes da
migration para a FK de tenant, o unique par `(tenant_id, id)` e os 22 índices
unique tenant-scoped. `scripts/audit_wave6_tenant_orm.ps1` compara o inventário
da migration com os models e com o registry central para detectar drift.

`MULTI_TENANT_WAVE6_ORM_ENABLED` é opt-in e permanece `false` quando ausente.
Essa flag apenas declara prontidão da camada de aplicação para uma futura onda;
ela não ativa rotas nem muda consultas nesta entrega.

**Schema não é isolamento.** Coluna, FK e unique compostos impedem parte dos
estados inconsistentes, mas não substituem filtro por tenant, verificação de
ownership e propagação de contexto em rotas, jobs, webhooks e caches. Por isso,
um segundo tenant continua bloqueado até a onda de aplicação e os testes em
PostgreSQL/VPS.

## Validação executada localmente

- revisão estática do encadeamento multi-tenant `20260731 -> 20260801 -> 20260802`;
- reconciliação das tabelas com `__tablename__` nos models e nas rotas;
- revisão 1:1 de relações, preflights e FKs compostas;
- `git diff --check` nos arquivos da onda.

O parser estático encontrou `20260802_tenant_marketing_crm_whatsapp_backfill`
como head desta cadeia. O repositório já possui outros heads históricos independentes;
esta onda não criou uma nova bifurcação, pois substituiu `20260731` como head apenas
na cadeia multi-tenant. A confirmação real ainda exige `alembic heads/history`.

Python, Alembic e PostgreSQL não estão disponíveis neste ambiente. Portanto,
`upgrade`, `downgrade`, `VALIDATE CONSTRAINT`, planos e contagens físicas não foram
executados. Isso deve integrar o futuro instalador/runbook da VPS antes de qualquer
ativação de segundo tenant.
