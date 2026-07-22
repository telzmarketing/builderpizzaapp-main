# SaaS Multiempresa — Seed do Tenant Legado

> Estado: migration criada, não executada
> Revisão: `20260722_legacy_tenant_seed`

## Escopo

A migration cria de forma aditiva e idempotente:

- tenant legado `tenant-legacy-default`, slug `legacy`;
- memberships para todos os registros atuais de `admin_users`;
- catálogo mínimo `platform_owner`, `platform_admin` e `platform_support`;
- permissões mínimas de empresas, auditoria e suporte;
- `platform_owner` explícito somente para usuários que hoje são master.

Nenhuma tabela de negócio recebe `tenant_id` nesta onda.

## Compatibilidade de papéis

- papel ausente ou `master`: membership `owner` e `platform_owner`;
- `administrador`: membership `admin`;
- `gerente`: membership `manager`;
- demais papéis: membership `operator`;
- usuário inativo: membership `suspended`, sem tenant padrão.

Os IDs do tenant, catálogo e vínculos são determinísticos. A execução repetida
usa `ON CONFLICT DO NOTHING`, sem duplicar registros ou substituir dados.

## Rollback

O downgrade remove somente vínculos e catálogo com IDs/prefixos reservados por
esta migration e o tenant legado com identidade exata. `admin_users`, papéis
RBAC legados e dados de negócio nunca são removidos.

O downgrade deve ser bloqueado se futuras tabelas passarem a referenciar o
tenant ou o catálogo. Nesse estágio, a reversão correta será uma migration
compensatória, preservando o histórico já tenantizado.

## Limitações

- migration ainda não validada contra PostgreSQL 15;
- não há backfill nem isolamento das tabelas de negócio;
- novos administradores criados após a migration precisam de membership pelo
  service de identidade, não por nova execução automática deste seed;
- a presença do tenant legado não autoriza operar um segundo tenant;
- login/JWT e seleção de tenant ainda dependem da integração Backend.
