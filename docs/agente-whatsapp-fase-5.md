# AGENTE WHATSAPP - Fase 5

## Objetivo

Permitir venda assistida pelo AGENTE WHATSAPP usando apenas ferramentas reais do ERP, sem inventar produto, preco, frete, cupom, pedido ou pagamento.

## Entregue

- Simulacao de checkout em `OrderService.quote_checkout`.
- Novas tools no registry do AGENTE WHATSAPP:
  - `validar_item_pedido`
  - `simular_checkout`
  - `criar_pedido`
  - `gerar_pagamento`
- Confirmacao explicita obrigatoria para tools mutantes.
- Eventos internos:
  - `agente_whatsapp_order_created`
  - `agente_whatsapp_payment_created`
- Auditoria segue em `agente_whatsapp_tool_calls`.

## Regras de seguranca

- `criar_pedido` exige `customer_confirmed = true` e `confirmation_text`.
- `gerar_pagamento` exige `customer_confirmed = true` e `confirmation_text`.
- Quando houver sessao/cliente no contexto, o pedido consultado ou pago precisa pertencer ao cliente da conversa.
- Cliente novo do WhatsApp pode virar lead automaticamente pelo telefone antes do pedido.
- O AGENTE WHATSAPP nao altera status de pedido nesta fase.
- O AGENTE WHATSAPP nao envia mensagem externa nesta fase.

## Fluxo esperado

1. Identificar telefone e sessao.
2. Buscar produtos/promocoes.
3. Validar item com `validar_item_pedido`.
4. Simular total com `simular_checkout`.
5. Apresentar resumo ao cliente.
6. Apenas apos confirmacao textual, chamar `criar_pedido`.
7. Apenas apos confirmacao textual, chamar `gerar_pagamento`.

## Fora do escopo da Fase 5

- Resposta autonoma da IA.
- Envio ativo pelo WhatsApp.
- Cancelamento ou edicao de pedido.
- Status automatico de pedido por WhatsApp.
- Takeover humano.
