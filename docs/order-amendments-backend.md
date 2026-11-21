# Alteracao de composicao do checkout: nucleo backend

## Contrato aditivo

- `POST /api/orders/{order_id}/amendments`: exige `pedidos.edit`, entitlement
  `orders.write` e header `Idempotency-Key`. Recebe `expected_revision` (inicial: 0),
  `expected_total`, `reason` e `items` no formato `CartItemIn` do checkout atual.
- `GET /api/orders/{order_id}/amendments?limit=50&offset=0`: exige `pedidos.view`.
  Retorna a revisao corrente e o historico da mais recente para a mais antiga.
- A resposta de alteracao contem uma revisao imutavel, com `before_snapshot`,
  `after_snapshot`, `actor_id`, `actor_name`, `created_at`, `reason` e `state`.
- A serializacao atual do pedido recebe apenas o campo aditivo
  `composition_revision`; os endpoints de criacao/status/fulfillment permanecem.

## Regras implementadas

O `OrderService` valida produtos, tamanhos, massas, bordas, variantes, sabores,
opcoes e precos pelo mesmo catalogo do checkout. Recalcula subtotal e desconto
manual ja existente, preserva o frete e confere `expected_total`. Identidade,
cliente, origem, endereco, forma de pagamento e estado do pedido nao mudam.
O valor do placeholder de pagamento pendente acompanha o novo total.
Nao ha cobranca, estorno, lancamento financeiro ou movimentacao de estoque.

Alteracao exige ausencia de inicio de producao, estado terminal e registros que
precisariam de reconciliacao. Neste nucleo, **tambem ficam bloqueados** pedidos:

- ja distribuidos no KDS, mesmo que ainda enfileirados;
- com snapshot de CMV, movimentacao/reserva de estoque, financeiro ou entrega;
- com pagamento liquidado ou PIX/link/transacao ja emitido pelo provedor;
- de aplicativos, salao/comanda, cupom, brinde ou pontos concedidos;
- com nova promocao que conceda brinde/frete gratis ou desconto antigo sem origem.

`paid`/`pago` em pagamento na entrega e apenas aceite operacional: pode ser
alterado se o pagamento continuar pendente, sem qualquer outro bloqueio.
Essas restricoes sao deliberadas: reconciliar KDS, custos, estoque e pagamentos
exige uma entrega posterior. Nao ha regra de perda/refeita neste escopo.

## Consistencia e persistencia

Tenant vem exclusivamente do ator autorizado. Revisao esperada e bloqueio do
pedido impedem sobrescrita por outra edicao. O inicio da criacao de pagamento
adquire o mesmo bloqueio, antes de ler o valor enviado ao gateway.

O `IdempotencyService` reserva a chave existente; composicao, historico e
conclusao da chave sao confirmados na mesma transacao. Falha desfaz a alteracao
e libera a chave. Replay retorna o historico originalmente confirmado, mesmo
que o pedido tenha sido alterado novamente. Outra composicao/ator/pedido com a
mesma chave retorna conflito. Nao ha nova emissao de `OrderCreated`.

Uma interrupcao abrupta do processo entre a reserva e a transacao pode deixar
a chave em `processing`, conforme o contrato atual do `IdempotencyService`.
Nesse caso o replay responde 409; consultar a revisao/historico antes de uma
nova tentativa com outra chave. A revisao esperada continua impedindo duplicacao.

A migration `20261120_order_amendments`, filha de `20261117_combo_landing`, cria
o historico e inicializa a revisao dos pedidos existentes em 0. A FK composta
protege o tenant do pedido; indices unicos protegem revisao e chave. Um trigger
PostgreSQL impede UPDATE/DELETE do historico. Nao aplicar o downgrade em dados
operacionais sem preservar o historico: ele remove a tabela de revisoes.

## Validacao

`python -m pytest -q tests/test_order_amendments.py` exercita persistencia,
recalculo, historico, replay, tenant, recusas, rollback e contrato HTTP.
SQLite nao comprova bloqueios PostgreSQL nem o trigger; a migration e o SQL de
bloqueio recebem verificacao especifica, sem aplicar migrations na base da loja.
