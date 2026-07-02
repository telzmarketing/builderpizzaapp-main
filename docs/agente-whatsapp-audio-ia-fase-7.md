# Agente WhatsApp Audio IA - Fase 7

Data: 2026-07-01

Status: executada funcionalmente no sistema.

## 1. Objetivo

Dar operacao administrativa ao audio do Agente WhatsApp: configurar saida por voz, visualizar audio/transcricao na conversa e executar retries manuais de STT/TTS.

## 2. Escopo entregue

- Configuracoes editaveis de audio na aba `Configuracoes` do Agente WhatsApp.
- Persistencia das configuracoes em `site_config`, chave `agente_whatsapp_audio`.
- Fallback automatico para variaveis `.env` quando nao houver configuracao persistida.
- Backend lendo configuracao persistida para decidir se gera TTS.
- Player de audio nas mensagens da conversa.
- Exibicao de transcricao e status STT em mensagens de audio.
- Botao manual para reprocessar STT em audio inbound.
- Botao manual para gerar voz/TTS em resposta textual da IA.
- Acao operacional para processar filas de STT, resposta IA, TTS e outbox.
- Contratos Pydantic e TypeScript atualizados.

## 3. Arquivos alterados

- `backend/routes/agente_whatsapp.py`
- `backend/schemas/agente_whatsapp.py`
- `backend/services/agente_whatsapp_audio_service.py`
- `backend/services/agente_whatsapp_audio_settings_service.py`
- `backend/services/agente_whatsapp_processing_service.py`
- `client/lib/api.ts`
- `client/pages/admin/crm/CrmAgenteWhatsApp.tsx`
- `docs/PLANO_EXECUCAO_WHATSAPP_AUDIO_IA.md`

## 4. Banco e migration

Nao houve migration nova.

A fase reaproveita:

- `site_config.content`
- `agente_whatsapp_messages`
- `agente_whatsapp_processing_jobs`
- `agente_whatsapp_audio_artifacts`
- `agente_whatsapp_outbox`

## 5. Endpoints adicionados

- `GET /api/agente-whatsapp/audio/settings`
- `PUT /api/agente-whatsapp/audio/settings`
- `POST /api/agente-whatsapp/messages/{message_id}/retry-tts`

Endpoints reutilizados no painel:

- `POST /api/agente-whatsapp/messages/{message_id}/retry-transcription`
- `POST /api/agente-whatsapp/processing/audio-transcriptions/process`
- `POST /api/agente-whatsapp/processing/agent-responses/process`
- `POST /api/agente-whatsapp/processing/tts-generations/process`
- `POST /api/agente-whatsapp/outbox/process`

## 6. Configuracoes editaveis

- `enabled`
- `response_mode`
- `tts_model`
- `tts_voice`
- `tts_format`
- `max_chars`
- `send_as_ptt`

Modos aceitos:

- `never`
- `mirror_customer_audio`
- `always`
- `manual_only`

## 7. Comportamento funcional entregue

Na aba `Configuracoes`:

1. O administrador visualiza e altera a saida por voz.
2. O painel salva a configuracao em `site_config`.
3. O worker passa a usar a configuracao persistida para gerar ou ignorar TTS.
4. O administrador pode processar filas de audio manualmente.

Na aba `Conversas`:

1. Mensagens de audio mostram player.
2. Audio inbound mostra status/transcricao STT.
3. Audio inbound pode ter STT reprocessado.
4. Resposta textual da IA pode gerar audio manualmente.

## 8. O que ficou fora desta fase

- Dashboard de custos STT/TTS.
- Metricas agregadas de conversao por audio.
- Validacao real em aparelhos WhatsApp.
- Configuracao por loja/tenant em interface separada.

Esses itens permanecem nas fases seguintes.

## 9. Validacao esperada

- `git diff --check`
- `npm.cmd run typecheck`
- `npm.cmd test`

Validacao real de envio de voz depende de runtime Baileys conectado, chave OpenAI e flags habilitadas.

## 10. Liberacao para Fase 8

A Fase 8 pode iniciar com foco em metricas, custos e conversoes:

- Contabilizar jobs STT/TTS.
- Medir falha, latencia e volume por provider.
- Relacionar audio/campanha/conversa/pedido.
- Expor indicadores gerenciais no painel.
