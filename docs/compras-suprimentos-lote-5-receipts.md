# Compras e Suprimentos — Lote 5: Recebimento

O lote adiciona recebimento físico separado do documento fiscal existente. O pedido precisa estar `confirmed`; documento fiscal informado precisa estar `validated` e vinculado ao pedido.

Fluxo: `draft → submitted → posted`. A postagem é idempotente, cria uma `InventoryOperation(kind="receipt")` e movimentos `source_type="receipt"`, sem criar obrigação financeira. Recebimentos parciais são aceitos, mas o acumulado publicado não pode exceder o pedido.

Rotas: `GET/POST /api/gestao/purchases/receipts`, `GET /api/gestao/purchases/receipts/{id}`, `POST /submit` e `POST /post`.

A migration `20261124_purchase_receipt_foundation` deve ser aplicada somente após a cadeia Alembic estar operacionalmente validada. A postagem online não foi executada neste lote.
