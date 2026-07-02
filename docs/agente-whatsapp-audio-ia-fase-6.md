# Agente WhatsApp Audio IA - Fase 6

Data: 2026-07-01

Status: executada funcionalmente no sistema.

## 1. Objetivo

Converter respostas textuais aprovadas do Agente WhatsApp em audio gerado por IA e enviar pelo Gateway Baileys como voice note/PTT quando a empresa habilitar a saida por audio.

## 2. Escopo entregue

- Configuracoes de saida por audio em `backend/config.py`.
- Metodo TTS em `OpenAIProvider`.
- Geracao de arquivo de audio a partir de resposta textual.
- Registro de artifact `tts` em `agente_whatsapp_audio_artifacts`.
- Criacao de mensagem outbound `audio` vinculada a resposta textual.
- Job operacional `tts_generation`.
- Processamento automatico de TTS no worker do Agente WhatsApp.
- Endpoint administrativo para processar TTS pendente.
- Envio de audio pelo outbox existente.
- Suporte a `media_type=audio` no Gateway Baileys.
- Payload Baileys com `ptt` para voice note.
- Resolucao de arquivos locais `/uploads/...` no runtime Node.
- Contratos Pydantic e TypeScript atualizados.

## 3. Arquivos alterados

- `backend/config.py`
- `backend/routes/agente_whatsapp.py`
- `backend/routes/whatsapp_marketing.py`
- `backend/schemas/agente_whatsapp.py`
- `backend/services/agente_whatsapp_audio_service.py`
- `backend/services/agente_whatsapp_outbox_service.py`
- `backend/services/agente_whatsapp_processing_service.py`
- `backend/services/agente_whatsapp_worker.py`
- `backend/services/ai/base.py`
- `backend/services/ai/openai_provider.py`
- `backend/services/whatsapp_gateway_baileys_provider.py`
- `backend/services/whatsapp_gateway_provider.py`
- `backend/services/whatsapp_gateway_runtime_client.py`
- `backend/services/whatsapp_gateway_service.py`
- `client/lib/api.ts`
- `server/whatsapp-gateway-runtime.mjs`
- `docs/PLANO_EXECUCAO_WHATSAPP_AUDIO_IA.md`

## 4. Banco e migration

Nao houve migration nova.

A fase reaproveita:

- `agente_whatsapp_processing_jobs`
- `agente_whatsapp_audio_artifacts`
- `agente_whatsapp_messages.media_url`
- `agente_whatsapp_messages.media_storage_key`
- `agente_whatsapp_messages.media_mime_type`
- `agente_whatsapp_messages.response_to_message_id`

## 5. Configuracoes

Padrao seguro:

- `WHATSAPP_AUDIO_OUTPUT_ENABLED=false`
- `WHATSAPP_AUDIO_RESPONSE_MODE=mirror_customer_audio`
- `WHATSAPP_AUDIO_TTS_MODEL=gpt-4o-mini-tts`
- `WHATSAPP_AUDIO_TTS_VOICE=marin`
- `WHATSAPP_AUDIO_TTS_FORMAT=opus`
- `WHATSAPP_AUDIO_TTS_MAX_CHARS=900`
- `WHATSAPP_AUDIO_TTS_SEND_AS_PTT=true`

Modos previstos:

- `never`: nunca gera audio.
- `mirror_customer_audio`: gera audio somente quando o cliente enviou audio.
- `always`: gera audio para toda resposta textual da IA.
- `manual_only`: reservado para uso manual futuro no painel.

## 6. Comportamento funcional entregue

Quando uma resposta textual da IA e gerada:

1. O job `agent_response` cria a resposta textual normalmente.
2. Se a saida por audio estiver habilitada, o sistema cria job `tts_generation`.
3. O job `tts_generation` gera audio com OpenAI TTS.
4. O arquivo e salvo em `uploads/agente-whatsapp-audio`.
5. O sistema cria uma mensagem outbound `audio`.
6. A mensagem de audio aponta `response_to_message_id` para a resposta textual.
7. A outbox envia o audio pelo Gateway Baileys.
8. O runtime Baileys envia como `audio` com `ptt=true`.

Endpoint adicionado:

- `POST /api/agente-whatsapp/processing/tts-generations/process`

## 7. Fallback

- Com `WHATSAPP_AUDIO_OUTPUT_ENABLED=false`, o sistema continua apenas em texto.
- Se o TTS falhar, a resposta textual ja permanece no fluxo normal da outbox.
- Se o Gateway falhar, a outbox segue com retry/dead item como nas mensagens atuais.

## 8. O que ficou fora desta fase

- Controles visuais no painel para ligar/desligar por empresa.
- Player e exibicao refinada de audio no painel.
- Metricas de custo STT/TTS.
- Teste real em Android, iPhone, WhatsApp Web e WhatsApp Desktop.

Esses itens permanecem nas fases seguintes.

## 9. Validacao esperada

- `git diff --check`
- `npm.cmd run typecheck`
- `npm.cmd test`

Validacao real com WhatsApp depende de runtime Baileys conectado, chave OpenAI configurada e flag de audio habilitada.

## 10. Liberacao para Fase 7

A Fase 7 pode iniciar com foco em configuracoes e experiencia do painel:

- Controles administrativos para `WHATSAPP_AUDIO_OUTPUT_ENABLED` e modo de resposta.
- Player de audio nas conversas.
- Exibicao de transcricao, TTS e status dos jobs.
- Retry manual de STT/TTS pelo painel.
