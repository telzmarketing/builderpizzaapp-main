# SaaS Multiempresa — Fase 1: Fundação Aditiva

> Data: 2026-07-21
> Estado: código implementado; migration não executada
> Ativação: desabilitada nas rotas e no JWT legado

## Entrega

A fundação adiciona, sem alterar tabelas de negócio ou contratos publicados:

- `tenants`;
- `tenant_memberships`;
- papéis e permissões explícitos da plataforma;
- vínculo entre usuário global e papel da plataforma;
- auditoria append-only da plataforma;
- `TenantContext` imutável e fail-closed;
- `TenantService` para tenant ativo, membership, seleção autorizada e soft delete;
- schemas Pydantic;
- testes unitários puros do contexto, hostname, ownership e slug;
- migration `20260721_multi_tenant_foundation`.

## Regras de segurança

- `tenant_id` enviado por body, query, header ou URL não é autoridade.
- Painel exige usuário, tenant ativo e membership ativa.
- Host público desconhecido não possui fallback para `default` ou tenant legado.
- Webhook/job só pode criar contexto a partir de metadata persistida e confiável.
- Recurso de tenant diferente falha por ownership.
- Tenant é removido logicamente por `status=disabled` e `deleted_at`.
- Apenas uma membership ativa pode ser padrão por usuário.
- Apenas um tenant legado não excluído pode existir.
- Slug é normalizado no service e possui unicidade case-insensitive no PostgreSQL.

## Compatibilidade

Nenhuma rota nova foi exposta. Login, JWT, RBAC e serviços atuais não foram alterados. A fundação não torna o sistema multiempresa por si só e não autoriza criar um segundo tenant operacional.

## Migration

`backend/migrations/versions/20260721_multi_tenant_foundation.py` está ancorada estaticamente em `20260704_campaign_contact_lists` e cria somente tabelas novas.

Não executado neste ambiente:

- import/compile Python;
- Alembic `heads/current`;
- upgrade/downgrade;
- seed do tenant legado;
- backfill de tabelas existentes.

Esses itens exigem Python 3.12 e PostgreSQL 15 local/staging.

## Próxima onda

Depois da validação da migration:

1. criar tenant legado e membership do administrador atual;
2. integrar seleção de tenant ao JWT/sessão sem quebrar o login;
3. adicionar dependency central de contexto;
4. executar primeiro slice `expand/backfill/contract` em identidade/RBAC;
5. somente então iniciar catálogo, clientes, pedidos e pagamentos.

## Validação disponível

```powershell
git diff --check
npm.cmd run typecheck
npm.cmd test
npm.cmd run build
```

Os testes Python foram escritos, mas só podem ser executados quando o runtime estiver disponível.
