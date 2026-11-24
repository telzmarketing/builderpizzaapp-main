# Compras e Suprimentos — Lote 3: Cotações

## Entrega

O lote implementa a fundação tenant-scoped de cotações e comparação normalizada:

- cotação criada somente a partir de requisição aprovada;
- fornecedores reutilizados de `InventorySupplier`;
- snapshot dos itens e quantidades da requisição;
- propostas por fornecedor e item;
- preço normalizado pelo fator de conversão informado;
- frete, desconto, prazo, validade e condição de pagamento;
- encerramento e adjudicação explícitos;
- idempotência nas escritas e controle de versão;
- RBAC server-side e FKs tenant-scoped.

## Rotas

`/api/gestao/purchases/quotations`

- `GET` lista;
- `GET /{id}` detalhe comparativo;
- `POST` cria a partir de requisição aprovada;
- `POST /{id}/open` abre;
- `POST /{id}/offers` registra ou atualiza proposta;
- `POST /{id}/close` encerra;
- `POST /{id}/award?supplier_id=...` adjudica fornecedor;
- `POST /{id}/cancel` cancela.

O lote não cria pedido de compra, não movimenta estoque e não gera obrigação financeira.

## Estados

`draft → open → closed → awarded`, com cancelamento em `draft` ou `open`.

Não há seleção automática por empate: a adjudicação exige ação autorizada e fornecedor com proposta.

## Interface

A seção `Cotações` do módulo de estoque exibe as cotações e o menor preço normalizado por item, com fornecedor e prazo. O envio por WhatsApp, e-mail ou PDF não é realizado automaticamente.
