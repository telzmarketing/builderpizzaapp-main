# Agente WhatsApp Audio IA - Fase 4

Data: 2026-07-01

Status: executada funcionalmente no sistema.

## 1. Objetivo

Fornecer ao Agente WhatsApp o contexto correto da campanha/oferta de origem ao responder mensagens de texto ou audio transcrito, sem inventar preco, cupom, validade ou beneficio quando o snapshot nao existir.

## 2. Escopo entregue

- Novo service `AgenteWhatsAppCampaignContextService`.
- Resolucao direta por `campaign_delivery_id` ja gravado na mensagem.
- Resolucao por `quoted_provider_message_id`.
- Resolucao por janela recente do telefone.
- Marcacao explicita de ambiguidade quando houver mais de uma campanha candidata.
- Persistencia do contexto em `agente_whatsapp_context`.
- Atualizacao segura de `campaign_delivery_id`, `campaign_id`, `conversation_id` e `replied_at` quando a campanha for resolvida.
- Inclusao do contexto no retorno de `ai/respond`.
- Regras no prompt do Agente para usar snapshot e perguntar em caso de ambiguidade.
- Ferramenta interna `resolver_contexto_campanha`.
- Endpoints administrativos para consulta/reprocessamento.
- Contratos Pydantic e TypeScript atualizados.

## 3. Arquivos alterados

- `backend/config.py`
- `backend/services/agente_whatsapp_campaign_context_service.py`
- `backend/services/agente_whatsapp_ai_service.py`
- `backend/services/agente_whatsapp_tools.py`
- `backend/routes/agente_whatsapp.py`
- `backend/schemas/agente_whatsapp.py`
- `client/lib/api.ts`
- `docs/PLANO_EXECUCAO_WHATSAPP_AUDIO_IA.md`

## 4. Banco e migration

Nao houve nova migration nesta fase.

A fase reaproveita:

- `whatsapp_campaign_deliveries`
- `agente_whatsapp_messages.campaign_delivery_id`
- `agente_whatsapp_messages.campaign_id`
- `agente_whatsapp_messages.quoted_provider_message_id`
- `agente_whatsapp_context.short_context_json`
- `agente_whatsapp_context.long_context_json`

## 5. Comportamento funcional entregue

Ao resolver contexto para uma mensagem inbound:

1. Se a mensagem ja tiver `campaign_delivery_id`, o sistema usa esse delivery.
2. Se houver `quoted_provider_message_id`, o sistema busca a mensagem/disparo citado.
3. Se nao houver quote, busca deliveries recentes do mesmo telefone na janela configurada.
4. A janela padrao e 72h, com prioridade para 24h.
5. Se houver uma candidata segura, a campanha e vinculada.
6. Se houver mais de uma candidata relevante, o status vira `ambiguous`.
7. Em caso ambiguo, a IA deve perguntar qual oferta o cliente quer antes de citar valores.
8. O snapshot usado vem de `whatsapp_campaign_deliveries`, nao do template/campanha atual editavel.

Endpoints adicionados:

- `GET /api/agente-whatsapp/sessions/{session_id}/campaign-context`
- `POST /api/agente-whatsapp/messages/{message_id}/resolve-campaign-context`

Ferramenta adicionada:

- `resolver_contexto_campanha`

## 6. O que ficou fora desta fase

- Resposta automatica completa a partir de jobs inbound.
- Criacao automatica de pedido a partir da oferta.
- Dashboard comercial completo.
- Correcao manual visual de ambiguidade no painel.

Esses itens permanecem nas fases seguintes.

## 7. Validacao executada

- `git diff --check`: passou.
- `npm.cmd run typecheck`: passou.
- `npm.cmd test`: passou com 7 arquivos e 33 testes.

Validacao nao executada:

- Compilacao Python local, porque este Windows nao possui `python` nem runtime no launcher `py`.

## 8. Riscos e observacoes

- Campanhas antigas podem ter snapshot limitado.
- Quando houver ambiguidade, o sistema nao escolhe oferta sozinho.
- `WHATSAPP_CAMPAIGN_CONTEXT_ENABLED=false` desliga a resolucao sem quebrar texto/audio.

## 9. Liberacao para Fase 5

A Fase 5 pode iniciar com foco em resposta textual IA, respeitando:

- Usar `transcription_text` como entrada quando vier de audio.
- Usar `campaign_context` somente quando estiver resolvido.
- Perguntar em caso de contexto ambiguo.
- Evitar resposta duplicada por job inbound.
