# AGENTE WHATSAPP - Fase 3

Data: 2026-05-13
Status: Implementacao do webhook inbound

## Objetivo

Receber mensagens reais de provedores WhatsApp e registrar a conversa no nucleo do `AGENTE WHATSAPP`, sem ativar IA, pedidos, pagamentos ou resposta automatica.

## Escopo implementado

- Webhook Meta Cloud API:
  - `GET /api/agente-whatsapp/webhook/meta`
  - `POST /api/agente-whatsapp/webhook/meta`
- Webhook Evolution:
  - `POST /api/agente-whatsapp/webhook/evolution`
- Identificacao por telefone.
- Criacao/reuso de lead WhatsApp usando a base da Fase 1.
- Criacao/reuso de sessao aberta usando o nucleo da Fase 2.
- Persistencia de mensagens inbound em `agente_whatsapp_messages`.
- Persistencia de eventos `agente_whatsapp_message_received`.
- Atualizacao de status de mensagens do agente quando o webhook Meta receber `statuses`.
- Protecao de duplicidade por `provider_message_id`.

## Regras preservadas

- O webhook antigo `/api/whatsapp/webhook` do disparador continua existindo.
- O novo webhook do agente nao envia resposta automatica.
- O novo webhook do agente nao cria pedido.
- O novo webhook do agente nao gera pagamento.
- O novo webhook do agente nao chama IA.
- O novo webhook do agente nao substitui campanhas existentes.

## Comportamento esperado

Quando uma mensagem chega:

1. O telefone do remetente e normalizado.
2. O sistema procura cliente/canal WhatsApp.
3. Se nao existir, cria lead.
4. O sistema procura sessao aberta para o telefone.
5. Se nao existir, cria sessao com origem `inbound`.
6. A mensagem e salva com `direction=inbound` e `sender_type=customer`.
7. Um evento interno do modulo e registrado.
8. A API retorna apenas o resumo do processamento.

## Fora de escopo

- Resposta automatica por IA.
- Atendimento humano realtime.
- Envio de mensagem pelo provider.
- Criacao de pedido pelo WhatsApp.
- Tool calling.
- Redis/workers/outbox.
- Painel visual.

## Criterios de aceite

- Payload Meta com `messages` cria/reusa lead e sessao.
- Payload Meta com `statuses` atualiza mensagem existente do agente.
- Payload Evolution `messages.upsert` cria/reusa lead e sessao.
- Webhook duplicado nao duplica mensagem.
- Validacoes frontend continuam passando.
