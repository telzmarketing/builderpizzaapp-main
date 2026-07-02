# Agente WhatsApp Audio IA - Fase 10

Data: 2026-07-01

Status: executada como preparacao operacional para piloto/deploy.

## 1. Objetivo

Transformar o pacote concluido nas Fases 0 a 9 em um roteiro executavel de piloto controlado na VPS, com migrations, rollback e validacoes pos-deploy.

## 2. Escopo entregue

- Workflow de deploy atualizado para rodar Alembic antes do build/restart.
- Target operacional de migration definido para `20260701_whatsapp_audio_phase5_agent_response`.
- Checklist de piloto consolidado para VPS.
- Criterios de entrada, aceite e rollback do piloto documentados.

## 3. Arquivos alterados

- `.github/workflows/deploy.yml`
- `docs/PLANO_EXECUCAO_WHATSAPP_AUDIO_IA.md`
- `docs/agente-whatsapp-audio-ia-fase-10.md`

## 4. Deploy automatizado

O workflow de producao agora executa, antes do build:

```bash
alembic -c backend/alembic.ini current
alembic -c backend/alembic.ini heads
alembic -c backend/alembic.ini upgrade 20260701_whatsapp_audio_phase5_agent_response
```

Isso reduz o risco de deploy com frontend/backend novo e banco atrasado para as tabelas/campos de audio.

## 5. Checklist de piloto VPS

Antes de liberar cliente real:

1. Confirmar que o deploy aplicou a revision `20260701_whatsapp_audio_phase5_agent_response`.
2. Conferir servicos:
   - `moschettieri-api`
   - `moschettieri-web`
   - `moschettieri-whatsapp-gateway`
3. Conferir readiness do modulo:
   - `/api/agente-whatsapp/audio/production-readiness`
4. Conferir jobs:
   - `/api/agente-whatsapp/processing/summary`
5. Conferir outbox:
   - `/api/agente-whatsapp/outbox/alerts`
6. Rodar cleanup em dry-run:
   - `/api/agente-whatsapp/audio/retention/cleanup?dry_run=true&limit=50`
7. Testar WhatsApp em:
   - Android
   - iPhone
   - WhatsApp Web
   - WhatsApp Desktop

## 6. Flags recomendadas para o primeiro piloto

```env
WHATSAPP_AUDIO_INPUT_ENABLED=true
WHATSAPP_AUDIO_TRANSCRIPTION_WORKER_ENABLED=true
WHATSAPP_CAMPAIGN_CONTEXT_ENABLED=true
WHATSAPP_AI_AUTO_REPLY_ENABLED=false
WHATSAPP_AUDIO_TTS_WORKER_ENABLED=false
WHATSAPP_AUDIO_TEXT_FALLBACK_ENABLED=true
WHATSAPP_AUDIO_LOW_CONFIDENCE_HANDOFF_ENABLED=true
WHATSAPP_AUDIO_RETENTION_CLEANUP_ENABLED=false
WHATSAPP_GATEWAY_AUDIO_BAILEYS_ENABLED=false
```

Com essa combinacao, o sistema recebe audio e pode transcrever, mas nao responde automaticamente nem envia voz para cliente real.

## 7. Evolucao gradual do piloto

1. Piloto 1: receber audio e validar transcricao no painel.
2. Piloto 2: habilitar resposta textual automatica para telefone controlado.
3. Piloto 3: habilitar TTS apenas para teste interno.
4. Piloto 4: habilitar modo espelho para poucos clientes reais.
5. Piloto 5: habilitar cleanup automatico depois de dry-run aprovado.

## 8. Rollback imediato

Para parar tudo de audio sem derrubar texto:

```env
WHATSAPP_AUDIO_INPUT_ENABLED=false
WHATSAPP_AUDIO_TRANSCRIPTION_WORKER_ENABLED=false
WHATSAPP_AI_AUTO_REPLY_ENABLED=false
WHATSAPP_AUDIO_TTS_WORKER_ENABLED=false
WHATSAPP_GATEWAY_AUDIO_BAILEYS_ENABLED=false
```

Texto, atendimento humano, pedidos, checkout, marketing e gateway continuam preservados.

## 9. Criterios de aceite

- Deploy aplica migrations sem erro.
- Backend responde `/health`.
- Gateway responde `pnpm whatsapp-gateway:health`.
- Readiness do audio retorna sem erro.
- Job summary nao mostra acumulo morto novo.
- Audio recebido aparece no painel com transcricao ou erro tratavel.
- Nenhuma resposta automatica e enviada enquanto `WHATSAPP_AI_AUTO_REPLY_ENABLED=false`.

## 10. Fora do escopo

- Executar deploy real na VPS a partir desta maquina local.
- Habilitar audio para todos os clientes.
- Criar RBAC granular novo.
- Migrar storage para URL privada/assinada.
