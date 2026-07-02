# Agente WhatsApp Audio IA - Fase 5

Data: 2026-07-01

Status: executada funcionalmente no sistema.

## 1. Objetivo

Fazer mensagens inbound elegiveis, incluindo audio transcrito, entrarem no fluxo textual do Agente WhatsApp com guardrails, revisao interna e envio pela outbox, sem gerar respostas duplicadas.

## 2. Escopo entregue

- Novo job operacional `agent_response`.
- Campo `response_to_message_id` em `agente_whatsapp_messages`.
- Vinculo entre resposta outbound e mensagem inbound de origem.
- Backfill de jobs para mensagens inbound ja existentes e elegiveis.
- Enfileiramento automatico de resposta textual para inbound de texto.
- Enfileiramento automatico apos STT concluido ou com baixa confianca.
- Processamento automatico no worker do Agente WhatsApp.
- Endpoint administrativo para processar respostas pendentes manualmente.
- Parametro `source_message_id` no fluxo `ai/respond`.
- Prevenção de resposta duplicada por mensagem de origem.
- Respeito a `session.ai_enabled`, `automation_blocked` e status humano/pausado/fechado.
- Fallback textual para audio com transcricao de baixa confianca.
- Contratos Pydantic e TypeScript atualizados.

## 3. Arquivos alterados

- `backend/config.py`
- `backend/models/agente_whatsapp.py`
- `backend/migrations/versions/20260701_whatsapp_audio_phase5_agent_response.py`
- `backend/routes/agente_whatsapp.py`
- `backend/schemas/agente_whatsapp.py`
- `backend/services/agente_whatsapp_ai_service.py`
- `backend/services/agente_whatsapp_processing_service.py`
- `backend/services/agente_whatsapp_service.py`
- `backend/services/agente_whatsapp_worker.py`
- `client/lib/api.ts`
- `docs/PLANO_EXECUCAO_WHATSAPP_AUDIO_IA.md`

## 4. Banco e migration

Migration adicionada:

- `20260701_whatsapp_audio_phase5_agent_response.py`

Mudancas:

- Adiciona `agente_whatsapp_messages.response_to_message_id`.
- Cria indice para consulta de resposta por mensagem de origem.
- Cria foreign key com `ON DELETE SET NULL`.
- Cria jobs `agent_response` para inbound de texto e audio ja transcrito.

## 5. Comportamento funcional entregue

Quando chega mensagem inbound:

1. O sistema registra a mensagem normalmente.
2. Mensagens de texto criam job `agent_response`.
3. Mensagens de audio criam job `audio_transcription`.
4. Ao concluir STT, o sistema cria job `agent_response`.
5. O job verifica se a sessao permite IA automatica.
6. Se a sessao estiver humana, pausada, fechada ou bloqueada, o job e marcado como ignorado.
7. Se ja existir resposta vinculada a mensagem de origem, nenhuma nova resposta e gerada.
8. Se o audio tiver baixa confianca, o sistema pede confirmacao em texto.
9. Se houver texto operacional, o Agente gera resposta textual com `manager_review`.
10. Respostas aprovadas sao colocadas na outbox para envio pelo canal ativo.

Endpoint adicionado:

- `POST /api/agente-whatsapp/processing/agent-responses/process`

Contrato de IA atualizado:

- `POST /api/agente-whatsapp/sessions/{session_id}/ai/respond`
- Campo opcional `source_message_id`.

## 6. O que ficou fora desta fase

- Geracao de voz por TTS.
- Envio de voice note/PTT.
- Player e controles visuais especificos no painel.
- Dashboard de metricas de STT/TTS.

Esses itens permanecem nas fases seguintes.

## 7. Validacao esperada

- `git diff --check`
- `npm.cmd run typecheck`
- `npm.cmd test`

Validacao Python depende de runtime Python local disponivel.

## 8. Riscos e observacoes

- A resposta automatica fica desligada por padrao e deve ser habilitada com `WHATSAPP_AI_AUTO_REPLY_ENABLED=true`.
- Guardrails do Agente ainda podem bloquear auto-envio quando detectarem excesso de respostas ou status inadequado.
- Audio com transcricao insegura nao vira resposta de negocio; o sistema solicita confirmacao textual.
- A Fase 6 deve reutilizar `response_to_message_id` para evitar voz duplicada.

## 9. Liberacao para Fase 6

A Fase 6 pode iniciar com foco em:

- Gerar TTS a partir da resposta textual aprovada.
- Salvar artefato de audio gerado.
- Enviar voice note/PTT pelo Gateway quando configurado.
- Manter fallback textual se TTS ou envio de audio falhar.
