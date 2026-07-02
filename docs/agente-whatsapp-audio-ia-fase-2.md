# Agente WhatsApp Audio IA - Fase 2

Data: 2026-07-01

Status: executada funcionalmente no sistema.

## 1. Objetivo

Criar a camada de entrada idempotente para mensagens inbound do Agente WhatsApp, preparando o pipeline para audio, STT e IA nas proximas fases sem duplicar conversas nem respostas.

## 2. Escopo entregue

- Campos de processamento em `agente_whatsapp_messages`.
- Nova fila interna `agente_whatsapp_processing_jobs`.
- Enfileiramento automatico de mensagem inbound ao persistir mensagem no Agente.
- Reuso idempotente quando o mesmo `provider_message_id` chegar mais de uma vez.
- Endpoints administrativos para resumo, listagem e enfileiramento de jobs inbound pendentes.
- Contratos Pydantic e TypeScript atualizados.

## 3. Arquivos alterados

- `backend/models/agente_whatsapp.py`
- `backend/services/agente_whatsapp_service.py`
- `backend/services/agente_whatsapp_processing_service.py`
- `backend/schemas/agente_whatsapp.py`
- `backend/routes/agente_whatsapp.py`
- `client/lib/api.ts`
- `backend/migrations/versions/20260701_whatsapp_audio_phase2_inbound_jobs.py`
- `docs/PLANO_EXECUCAO_WHATSAPP_AUDIO_IA.md`

## 4. Banco e migration

Migration criada:

- `20260701_whatsapp_audio_phase2_inbound_jobs.py`

Entrega da migration:

- Adiciona em `agente_whatsapp_messages`:
  - `processing_status`
  - `idempotency_key`
  - `processed_at`
- Cria `agente_whatsapp_processing_jobs`.
- Cria indices de status, mensagem, sessao, cliente, tipo de job e proxima tentativa.
- Cria unique parcial em `agente_whatsapp_messages.idempotency_key`.
- Faz backfill de mensagens inbound existentes para jobs pendentes.

## 5. Comportamento funcional entregue

Ao receber ou registrar mensagem inbound:

1. O sistema preserva a deduplicacao por `provider_message_id`.
2. A mensagem recebe `processing_status = recorded`.
3. A mensagem e enfileirada como job `inbound_message`.
4. O job usa chave idempotente `inbound_message:<message_id>`.
5. A mensagem passa para `processing_status = queued`.
6. Se o mesmo evento chegar novamente, o sistema reutiliza a mensagem/job existente.

Endpoints administrativos adicionados:

- `GET /api/agente-whatsapp/processing/summary`
- `GET /api/agente-whatsapp/processing/jobs`
- `POST /api/agente-whatsapp/processing/enqueue`

## 6. O que ficou fora desta fase

- Download de audio.
- Transcricao STT.
- TTS.
- Resposta automatica por IA a partir do job.
- Worker de processamento pesado.
- UI operacional para a fila inbound.

Esses itens permanecem nas fases seguintes.

## 7. Validacao executada

- `git diff --check`: passou.
- `npm.cmd run typecheck`: passou.
- `npm.cmd test`: passou com 7 arquivos e 33 testes.

Validacao nao executada:

- Compilacao Python local, porque este Windows nao possui `python` nem runtime no launcher `py`.

## 8. Riscos e observacoes

- A migration ainda precisa ser aplicada na VPS antes de usar a fase em producao.
- A fila inbound ainda e preparatoria: ela organiza entrada e idempotencia, mas nao executa STT/TTS.
- O processamento pesado deve consumir `agente_whatsapp_processing_jobs` em fase posterior, respeitando `status`, `attempts`, `max_attempts` e `idempotency_key`.

## 9. Liberacao para Fase 3

A Fase 3 pode iniciar com foco em audio inbound e STT, respeitando:

- Usar `agente_whatsapp_processing_jobs` como ponto de entrada.
- Nao bloquear o webhook durante processamento pesado.
- Manter texto atual funcionando mesmo com audio desabilitado.
- Gravar falhas sem duplicar respostas.
