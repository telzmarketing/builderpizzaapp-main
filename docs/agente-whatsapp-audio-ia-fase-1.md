# Agente WhatsApp Audio IA - Fase 1

Data: 2026-07-01

Status: executada funcionalmente no sistema.

## 1. Objetivo

Criar a base funcional para rastrear campanhas/disparos do Marketing ate a conversa do Agente WhatsApp, sem implementar audio, STT, TTS ou resposta por voz.

## 2. Escopo entregue

- Nova entidade funcional de delivery/snapshot de campanha.
- Backfill conceitual via migration a partir de `whatsapp_messages`.
- Vinculo de delivery com mensagem outbound sincronizada no Agente.
- Campos de campanha/delivery nas mensagens do Agente.
- Captura inicial de `quoted_provider_message_id` em inbound Meta, Evolution e Baileys runtime.
- Exposicao de `campaign_delivery_id` no monitoramento de WhatsApp Marketing.
- Contratos Pydantic e TypeScript atualizados.

## 3. Arquivos alterados

- `backend/routes/whatsapp_marketing.py`
- `backend/models/agente_whatsapp.py`
- `backend/schemas/agente_whatsapp.py`
- `backend/routes/agente_whatsapp.py`
- `backend/services/agente_whatsapp_service.py`
- `backend/database.py`
- `server/whatsapp-gateway-runtime.mjs`
- `client/lib/api.ts`
- `client/pages/admin/marketing/MarketingWhatsApp.tsx`
- `backend/migrations/versions/20260701_whatsapp_audio_phase1_deliveries.py`
- `docs/PLANO_EXECUCAO_WHATSAPP_AUDIO_IA.md`

## 4. Banco e migration

Migration criada:

- `20260701_whatsapp_audio_phase1_deliveries.py`

Entrega da migration:

- Cria `whatsapp_campaign_deliveries`.
- Adiciona em `agente_whatsapp_messages`:
  - `provider`
  - `quoted_provider_message_id`
  - `campaign_id`
  - `campaign_delivery_id`
- Cria indices para consulta por provider, quoted id, campaign id, delivery id, telefone e status.
- Cria unique parcial em `(provider, provider_message_id)` para deliveries com provider id.
- Faz backfill a partir de `whatsapp_messages`.
- Vincula mensagens existentes do Agente quando o `provider_message_id` bater com delivery.

## 5. Comportamento funcional entregue

Ao disparar mensagem no Marketing WhatsApp:

1. O sistema cria o registro atual em `whatsapp_messages`.
2. O sistema cria um delivery pendente em `whatsapp_campaign_deliveries`.
3. O envio e feito pelo provider atual.
4. O delivery recebe `provider_message_id`, status, snapshot do texto, midia, template, campanha e destinatario.
5. Quando o envio e sincronizado com o Agente, a mensagem outbound recebe `campaign_delivery_id` e `campaign_id`.
6. O delivery grava `conversation_id` e `agente_message_id`.

No webhook de status da Meta:

1. `whatsapp_messages` continua sendo atualizado.
2. `whatsapp_campaign_deliveries` tambem passa a ser atualizado com status, timestamps e payload do provider.

No inbound do Agente:

- Meta tenta capturar `context.id`.
- Evolution tenta capturar `contextInfo.stanzaId`.
- Baileys runtime passa a enviar `quoted_provider_message_id` quando houver `contextInfo.stanzaId`.

## 6. O que ficou fora desta fase

- Download de audio.
- Transcricao STT.
- TTS.
- Envio de audio/voice note.
- Player de audio no painel.
- Resolucao completa por janela de 72h.
- Tratamento visual de ambiguidade.
- Metricas de custo e conversao.

Esses itens permanecem nas fases seguintes.

## 7. Validacao executada

- `git diff --check`: passou.
- `npm.cmd run typecheck`: passou.
- `npm.cmd test`: passou com 7 arquivos e 33 testes.

Validacao nao executada:

- Compilacao Python local, porque este Windows nao possui `python` nem runtime no launcher `py`.

## 8. Riscos e observacoes

- A migration ainda precisa ser aplicada na VPS antes de usar a fase em producao.
- A tabela `whatsapp_campaign_deliveries` nasce como fonte canonica de delivery, mas o fluxo antigo `whatsapp_messages` foi preservado.
- `quoted_provider_message_id` agora pode ser persistido, mas a resolucao automatica completa de campanha por quote/janela sera aprofundada nas fases seguintes.
- O runtime Baileys apenas passa a carregar o id da mensagem citada; envio de audio continua fora desta fase.

## 9. Liberacao para Fase 2

A Fase 2 pode iniciar com foco em entrada/idempotencia e processamento inbound, respeitando:

- Nao implementar STT/TTS ainda.
- Usar `campaign_delivery_id` e `quoted_provider_message_id` criados na Fase 1.
- Manter Marketing como origem dos disparos.
- Preservar o fluxo textual atual.
