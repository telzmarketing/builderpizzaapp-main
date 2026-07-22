# Onda multiempresa: operacao, frete, entrega e salao

## Escopo comprovado

Esta onda encadeia `20260730_tenant_operations_expand` e
`20260731_tenant_operations_backfill` depois de
`20260729_tenant_payments_backfill`. Foram inventariadas 26 tabelas ORM:
5 de logistica/entrega, 11 de frete V1/V2, 5 de salao/pagina publica e
5 de funcionamento da loja.

`geocode_cache` nao foi tenantizada: permanece cache potencialmente
compartilhado, condicionado a chave normalizada, ausencia de PII persistida e
expiracao. Nao existe tabela especifica de cozinha; o fluxo comprovado usa
`orders.status`, e `orders` pertence a uma onda anterior.

## Estrategia

O expand adiciona `tenant_id` nullable e sem default nas 21 tabelas que ainda
nao tinham a coluna. Nas cinco `store_operation_*`, relaxa a coluna legada para
nullable e remove eventual default de servidor antes de adicionar FK, indice
`(tenant_id, id)` e relacao composta. Todas as FKs
novas usam `NOT VALID`.

O backfill idempotente converte `NULL` e `default` para
`tenant-legacy-default`. Antes de escrever, verifica tenant legado, rotulos
desconhecidos, duplicatas scoped e ownership das FKs compostas.

Foram criadas unicidades por tenant para configuracoes singleton, email do
entregador, pedido por entrega, tipo de frete e numero de mesa. As relacoes
compostas cobrem entrega/pedido/motoboy, eventos e ganhos, zonas de frete,
reservas, sessoes/itens de mesa e intervalos de funcionamento.

Nenhuma coluna recebe `NOT NULL`, nenhuma FK e validada e nenhuma constraint
global antiga e removida. A PK global `id` ainda impede repetir IDs como
`default` entre tenants; alterar PK e remover uniques globais pertence ao
contract, apos dual-read/write, testes A/B e snapshot fisico.

## Alinhamento ORM e runtime

Os 26 models ORM agora espelham `tenant_id` nullable e sem default, as FKs
simples nomeadas para `tenants.id`, os 26 indices unicos
`(tenant_id, id)` e as oito unicidades scoped do expand. As FKs compostas
continuam somente na migration: replica-las nos relacionamentos ORM mudaria a
resolucao de joins antes da ativacao do slice.

`TENANT_OPERATIONS_ENFORCEMENT_ENABLED` permanece `False` por padrao. O
helper `operations_enforcement_enabled()` permite que rotas sejam migradas
individualmente com `TenantContext` confiavel e os helpers de ownership.
Nenhuma rota desta onda foi marcada como isolada por esta alteracao; com a flag
desligada, o comportamento legado continua inalterado.

## Riscos e validacao futura

- tabelas criadas por DDL historico precisam existir no PostgreSQL real;
- preflights podem bloquear duplicatas ou ownership divergente;
- rotulos diferentes de `default` precisam existir em `tenants`;
- constraints globais antigas seguem mais restritivas ate o contract;
- Alembic/Python/PostgreSQL nao foram executados neste ambiente.

Na VPS/staging: restaurar backup, confirmar `heads/current`, aplicar expand e
backfill separadamente, registrar counts antes/depois e confirmar zero
NULL/mismatch antes de planejar `VALIDATE CONSTRAINT`.
