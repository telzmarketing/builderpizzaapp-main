# Agente WhatsApp Audio IA - Fase 3

Data: 2026-07-01

Status: executada funcionalmente no sistema.

## 1. Objetivo

Implementar recepcao, armazenamento, validacao e transcricao STT de audio inbound no Agente WhatsApp, sem responder em audio e sem acoplar processamento pesado ao webhook.

## 2. Escopo entregue

- Campos de audio e transcricao em `agente_whatsapp_messages`.
- Nova tabela `agente_whatsapp_audio_artifacts`.
- Job `audio_transcription` para mensagens inbound de audio.
- Worker do Agente processando transcricoes pendentes em lote.
- Servico `AgenteWhatsAppAudioService` para download, validacao, storage e STT OpenAI.
- Download de audio Meta Cloud quando `media_url` for ID do provider.
- Download/local storage de audio Baileys no runtime quando possivel.
- Endpoint administrativo para processar lote de transcricoes.
- Endpoint administrativo para retry de transcricao por mensagem.
- Upload administrativo passa a aceitar audio para testes internos.
- Contratos Pydantic e TypeScript atualizados.

## 3. Arquivos alterados

- `backend/config.py`
- `backend/models/agente_whatsapp.py`
- `backend/migrations/versions/20260701_whatsapp_audio_phase3_audio_stt.py`
- `backend/services/agente_whatsapp_audio_service.py`
- `backend/services/agente_whatsapp_processing_service.py`
- `backend/services/agente_whatsapp_service.py`
- `backend/services/agente_whatsapp_worker.py`
- `backend/services/ai/base.py`
- `backend/services/ai/openai_provider.py`
- `backend/routes/agente_whatsapp.py`
- `backend/routes/upload.py`
- `backend/schemas/agente_whatsapp.py`
- `client/lib/api.ts`
- `server/whatsapp-gateway-runtime.mjs`
- `docs/PLANO_EXECUCAO_WHATSAPP_AUDIO_IA.md`

## 4. Banco e migration

Migration criada:

- `20260701_whatsapp_audio_phase3_audio_stt.py`

Entrega da migration:

- Adiciona em `agente_whatsapp_messages`:
  - `media_storage_key`
  - `media_mime_type`
  - `media_duration_ms`
  - `media_size_bytes`
  - `transcription_status`
  - `transcription_text`
  - `transcription_language`
  - `transcription_provider`
  - `transcription_model`
  - `transcription_error`
  - `transcription_quality_json`
- Cria `agente_whatsapp_audio_artifacts`.
- Cria jobs `audio_transcription` para audios inbound existentes.

## 5. Comportamento funcional entregue

Ao receber mensagem inbound de audio:

1. O Agente registra a mensagem como `message_type = audio`.
2. A Fase 2 cria job idempotente; agora audio usa `audio_transcription:<message_id>`.
3. O worker do Agente busca jobs `audio_transcription` pendentes.
4. O servico tenta carregar o audio:
   - `/uploads/...` local.
   - URL `http(s)`.
   - ID Meta Cloud via Graph API e credencial `whatsapp_cloud`.
   - Arquivo baixado pelo runtime Baileys quando disponivel.
5. O sistema valida MIME e tamanho.
6. O arquivo e salvo em `uploads/agente-whatsapp-audio`.
7. A transcricao roda com `gpt-4o-mini-transcribe`.
8. Se falhar ou houver baixa qualidade, tenta `gpt-4o-transcribe`.
9. A transcricao final fica em `transcription_text` e tambem preenche `body` se a mensagem nao tiver texto.

Endpoints adicionados:

- `POST /api/agente-whatsapp/processing/audio-transcriptions/process`
- `POST /api/agente-whatsapp/messages/{message_id}/retry-transcription`

## 6. O que ficou fora desta fase

- Resposta automatica textual por IA a partir da transcricao.
- Contexto de campanha por quote/janela.
- Envio de audio/voice note.
- TTS.
- Player visual no painel.
- Metricas de custo STT/TTS.

Esses itens permanecem nas fases seguintes.

## 7. Validacao executada

- `git diff --check`: passou.
- `npm.cmd run typecheck`: passou.
- `npm.cmd test`: passou com 7 arquivos e 33 testes.

Validacao nao executada:

- Compilacao Python local, porque este Windows nao possui `python` nem runtime no launcher `py`.
- Transcricao real OpenAI, porque exige chave e chamada externa no ambiente de execucao.

## 8. Riscos e observacoes

- A migration precisa ser aplicada na VPS antes de usar em producao.
- Para Meta Cloud, o download depende da credencial `whatsapp_cloud` ja cadastrada.
- Para Baileys, o runtime tenta baixar o arquivo no evento inbound; se falhar, a mensagem ainda e registrada e a transcricao falha de forma segura.
- `WHATSAPP_AUDIO_INPUT_ENABLED=false` desliga a transcricao sem quebrar conversa textual.
- O uso real de STT gera custo no provedor OpenAI.

## 9. Liberacao para Fase 4

A Fase 4 pode iniciar com foco em contexto de campanha, respeitando:

- Usar `transcription_text` como texto operacional do cliente.
- Nao inventar campanha se houver ambiguidade.
- Preservar `campaign_delivery_id` e `quoted_provider_message_id` da Fase 1.
- Manter fallback humano quando a transcricao estiver `low_confidence` ou `failed`.
