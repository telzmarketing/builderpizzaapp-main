# Multiempresa - Runtime de operacoes e backoffice

## Escopo comprovado nesta onda

- Foi criado `backend/core/tenant_route_context.py` como ponto unico para dependencias HTTP da Wave 5.
- Com `TENANT_OPERATIONS_ENFORCEMENT_ENABLED=false`, `operation_tenant_id()` preserva integralmente o singleton legado `default`.
- Com a Wave 5 ligada, o contexto deixa de aceitar fallback: rotas administrativas exigem contexto resolvido por JWT e membership ativa; rotas publicas exigem dominio ativo.
- `GET /api/gestao/cmv/overview` agora instancia `CmvService` com o tenant membership-backed. As consultas internas do service ja filtravam configuracao, receitas, movimentos e snapshots por `tenant_id`.

## Ordem segura de ativacao

`TENANT_OPERATIONS_ENFORCEMENT_ENABLED` nao deve ser ligada isoladamente. Para painel, exige `MULTI_TENANT_AUTH_ENABLED=true`; para endpoints publicos que forem migrados, exige `TENANT_DOMAINS_ENABLED=true`. Antes da ativacao, o backfill e as constraints da respectiva onda precisam estar aplicados e validados no PostgreSQL.

## Lacunas que continuam bloqueando isolamento completo

- Estoque, financeiro, fiscal e configuracoes gerais de gestao possuem services tenant-aware, mas suas rotas ainda os instanciam com o tenant legado. Devem ser migradas por modulo, cobrindo todos os reads, writes e lookups por ID em uma mesma ativacao.
- Operacao da loja usa `tenant_id` internamente, mas o endpoint publico de status e os endpoints administrativos ainda nao resolvem host/membership.
- Frete e salao ainda precisam receber `TenantContext` nos services. Nao basta filtrar apenas as listas: configuracoes singleton, calculo publico, reservas, mesas, sessoes e transicoes por ID precisam compartilhar o mesmo ownership.
- Integracoes cruzadas (pedido para estoque/CMV, sessao de mesa para pedido e documento fiscal a partir de pedido) precisam validar que origem e destino pertencem ao mesmo tenant.

Enquanto essas lacunas existirem, a flag de operacoes deve permanecer desligada fora de testes controlados do endpoint CMV. Este documento nao declara isolamento dos modulos pendentes.
