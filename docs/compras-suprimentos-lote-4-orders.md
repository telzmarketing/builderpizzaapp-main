# Compras e Suprimentos — Lote 4: Pedidos de Compra

## Entrega

O Pedido de Compra continua sendo o `InventoryPurchase` canônico. Não foi criada uma tabela paralela de compras.

Foram adicionados:

- vínculo com cotação adjudicada e requisição;
- snapshot da adjudicação;
- versão concorrente;
- fornecedor e proposta de origem por item;
- criação idempotente a partir de cotação adjudicada;
- transições explícitas `draft → requested → confirmed`;
- aprovação com `expected_version`;
- bloqueio de reutilização da mesma proposta em dois pedidos.

## Rotas

- `POST /api/gestao/inventory/purchases/from-quotation`
- `POST /api/gestao/inventory/purchases/{id}/submit`
- `POST /api/gestao/inventory/purchases/{id}/approve`

O pedido aprovado/confirmado não movimenta estoque diretamente. O recebimento permanece no fluxo oficial de documentos e entradas.

Pedidos originados de cotação não publicam a projeção financeira legada no momento da aprovação; a fronteira financeira permanece no recebimento/reconciliação fiscal.

## Controles

- tenant obtido do contexto autenticado;
- cotação deve estar adjudicada para o fornecedor informado;
- todas as propostas da cotação precisam cobrir os itens;
- `Idempotency-Key` obrigatório nas escritas;
- versão obrigatória nas transições;
- pedido confirmado não deve ser editado pelo fluxo genérico.

## Gate operacional

A migration `20261124_purchase_order_provenance` foi criada, mas ainda não foi aplicada online. A cadeia Alembic precisa ser corrigida/confirmada antes de release.
