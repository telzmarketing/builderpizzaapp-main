# Agente WhatsApp Audio IA - Fase 9

Data: 2026-07-01

Status: executada funcionalmente no sistema.

## 1. Objetivo

Preparar o fluxo de audio/IA do Agente WhatsApp para operacao real com rollback por flags, observabilidade operacional, retencao de audio e checklist de deploy.

## 2. Escopo entregue

- Flags operacionais de producao para STT, TTS, fallback textual, baixa confianca, cleanup e envio de audio Baileys.
- Bloqueio efetivo do envio de audio via Gateway Baileys quando a flag estiver desligada.
- Worker respeitando flags de transcricao, TTS e cleanup.
- Endpoint de readiness operacional.
- Endpoint de retencao/cleanup com `dry_run=true` por padrao.
- Service de retencao para apagar arquivos antigos apenas dentro do diretorio configurado de audio.
- Contratos frontend em `client/lib/api.ts` para readiness e cleanup.
- Checklist de rollback e VPS documentado nesta fase.

## 3. Arquivos alterados

- `backend/config.py`
- `backend/routes/agente_whatsapp.py`
- `backend/schemas/agente_whatsapp.py`
- `backend/services/agente_whatsapp_audio_service.py`
- `backend/services/agente_whatsapp_outbox_service.py`
- `backend/services/agente_whatsapp_processing_service.py`
- `backend/services/agente_whatsapp_retention_service.py`
- `backend/services/agente_whatsapp_worker.py`
- `backend/services/whatsapp_gateway_service.py`
- `client/lib/api.ts`
- `docs/PLANO_EXECUCAO_WHATSAPP_AUDIO_IA.md`

## 4. Endpoints operacionais

- `GET /api/agente-whatsapp/audio/production-readiness`
- `POST /api/agente-whatsapp/audio/retention/cleanup?dry_run=true&limit=50`

O cleanup real exige `dry_run=false`. Por padrao ele apenas calcula o que seria elegivel para remocao.

## 5. Flags

- `WHATSAPP_AUDIO_INPUT_ENABLED`
- `WHATSAPP_AUDIO_TRANSCRIPTION_WORKER_ENABLED`
- `WHATSAPP_AI_AUTO_REPLY_ENABLED`
- `WHATSAPP_AUDIO_TTS_WORKER_ENABLED`
- `WHATSAPP_AUDIO_TEXT_FALLBACK_ENABLED`
- `WHATSAPP_AUDIO_LOW_CONFIDENCE_HANDOFF_ENABLED`
- `WHATSAPP_AUDIO_RETENTION_CLEANUP_ENABLED`
- `WHATSAPP_AUDIO_RETENTION_DAYS`
- `WHATSAPP_AUDIO_RETENTION_BATCH_SIZE`
- `WHATSAPP_GATEWAY_AUDIO_BAILEYS_ENABLED`

## 6. Retencao/LGPD

O cleanup:

1. Busca artifacts `stored` ou `generated` criados antes da janela de retencao.
2. Garante que o arquivo esta dentro de `WHATSAPP_AUDIO_STORAGE_DIR`.
3. Remove o arquivo fisico somente quando `dry_run=false`.
4. Marca o artifact como `deleted`.
5. Limpa `media_url`, `media_storage_key` e tamanho da mensagem quando nao houver outro artifact ativo.

Nao houve migration nova nesta fase. A auditoria minima e preservada pelo proprio registro do artifact.

## 7. Rollback

- Desligar `WHATSAPP_AUDIO_INPUT_ENABLED` para parar STT.
- Desligar `WHATSAPP_AI_AUTO_REPLY_ENABLED` para parar resposta automatica.
- Desligar a saida de audio nas configuracoes do Agente para parar TTS.
- Desligar `WHATSAPP_AUDIO_TTS_WORKER_ENABLED` para parar jobs TTS.
- Desligar `WHATSAPP_GATEWAY_AUDIO_BAILEYS_ENABLED` para bloquear envio de audio no Gateway.
- Manter texto, atendimento humano, pedidos, checkout, Marketing e Gateway sem audio funcionando.

## 8. Checklist VPS

Antes do restart:

```bash
git pull origin main
source .venv/bin/activate
alembic -c backend/alembic.ini current
alembic -c backend/alembic.ini heads
alembic -c backend/alembic.ini upgrade 20260605_whatsapp_gateway_base
npm run build
```

Depois do restart:

```bash
systemctl restart moschettieri-api
systemctl restart moschettieri-web
systemctl restart moschettieri-whatsapp-gateway
systemctl status moschettieri-api --no-pager
systemctl status moschettieri-whatsapp-gateway --no-pager
```

Validacoes administrativas:

- Abrir `/api/agente-whatsapp/audio/production-readiness`.
- Conferir `/api/agente-whatsapp/processing/summary`.
- Conferir `/api/agente-whatsapp/outbox/alerts`.
- Rodar cleanup em dry-run antes de habilitar automatico.
- Validar envio e reproducao em Android, iPhone, WhatsApp Web e Desktop.

## 9. Validacao esperada

- `git diff --check`
- `npm.cmd run typecheck`
- `npm.cmd test`
- `npm.cmd run build`

Validacao Python local pode ficar indisponivel no Windows se o runtime Python nao estiver instalado.

## 10. Liberacao

Com a Fase 9, o pacote de Audio/IA esta pronto para piloto controlado. A expansao real deve ser gradual, com flags conservadoras e fallback textual ligado.
