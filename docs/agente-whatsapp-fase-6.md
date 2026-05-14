# AGENTE WHATSAPP - Fase 6

## Objetivo

Registrar automaticamente mensagens de status de pedidos no AGENTE WHATSAPP a partir dos eventos reais do ERP.

## Entregue

- Service `AgenteWhatsAppStatusService`.
- Assinaturas no event bus em `backend/main.py`.
- Criacao/reuso de sessao com origem `order_status`.
- Mensagens de status gravadas em `agente_whatsapp_messages` como:
  - `direction = outbound`
  - `sender_type = system`
  - `message_type = status`
  - `provider_status = queued`
- Eventos gravados em `agente_whatsapp_events` com source `order_status`.
- Protecao contra duplicidade por `order_id + event_type + source`.

## Eventos cobertos

- `OrderCreated` -> `order_created`
- `PaymentConfirmed` -> `payment_approved`
- `PaymentFailed` -> `payment_failed`
- `OrderStatusChanged`:
  - `preparing` -> `order_preparing`
  - `ready_for_pickup` -> `order_ready`
  - `on_the_way` -> `order_out_delivery`
  - `delivered` -> `order_delivered`
  - `cancelled` -> `order_cancelled`
- `OrderCancelled` -> `order_cancelled`
- `DeliveryAssigned` -> `order_out_delivery`
- `DeliveryCompleted` -> `order_delivered`

## Regras de seguranca

- A Fase 6 nao envia mensagem externa ao provedor WhatsApp.
- A Fase 6 nao cria worker Redis.
- A Fase 6 nao altera status de pedido.
- A Fase 6 nao altera pagamento.
- Se o pedido nao tiver telefone, nenhuma mensagem e criada.
- Se a mesma notificacao ja foi registrada para o pedido, ela nao e duplicada.

## Proxima fase

A Fase 7 deve criar a central operacional visual do AGENTE WHATSAPP para acompanhar conversas, mensagens e status em painel. O envio real por provider e fila assíncrona deve ficar para a Fase 8, conforme o plano original.
