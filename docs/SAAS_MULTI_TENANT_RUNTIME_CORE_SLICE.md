# Slice runtime central: catalogo, clientes e pedidos

## Escopo implementado

- Resolucao confiavel do tenant de painel por JWT e membership ativa, somente com `MULTI_TENANT_AUTH_ENABLED=true`.
- Resolucao confiavel da loja por dominio ativo, somente com `TENANT_DOMAINS_ENABLED=true`; `X-Forwarded-Host` continua condicionado a proxy e IP explicitamente confiaveis.
- `OrderService`: ownership na criacao de pedido, pagamento, itens e sabores; consultas por ID, listagem e codigo do pedido com escopo; validacao central de cliente e produtos com escopo.
- Pedidos HTTP: checkout publico, listagem, detalhe, status de pagamento, alteracao/cancelamento/exclusao admin, cancelamento do cliente, relatorio operacional e auto-cancelamento.
- Clientes HTTP: listagem/detalhe admin, cadastro/edicao publico, enderecos e historico de pedidos.
- Catalogo HTTP: listagem/detalhe/cotacao publica; CRUD de produto e categorias no painel.

## Compatibilidade e ativacao

As flags permanecem `false` por padrao. Com elas desligadas, os resolvedores retornam `None` antes de ler host/header, e os helpers de query/criacao mantem exatamente o caminho global legado. Ativar enforcement sem ativar/resolver o contexto correspondente falha fechado.

Ordem minima de ativacao:

1. migrations, backfill e validacao de `tenant_id` concluidos;
2. `MULTI_TENANT_AUTH_ENABLED=true` para o painel;
3. `TENANT_DOMAINS_ENABLED=true` para lojas publicas;
4. `TENANT_IDENTITY_CATALOG_ENFORCEMENT_ENABLED=true` e/ou `TENANT_CUSTOMERS_ORDERS_ENFORCEMENT_ENABLED=true` apenas depois dos passos anteriores.

## Fora desta cobertura

Ainda nao declaram isolamento runtime completo: configuracoes singleton de catalogo, promocoes de produto, tamanhos/massas/variantes em seus endpoints administrativos, identidade WhatsApp/IA de clientes, eventos comportamentais e servicos transversais chamados pelo checkout (cupons, frete, estoque e notificacoes). Os campos/migrations dessas areas nao equivalem a isolamento de rota.
