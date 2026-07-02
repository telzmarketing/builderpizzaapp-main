# Agente WhatsApp Audio/IA - Fase 12

Data: 2026-07-01

## Objetivo

Permitir controle operacional do rollout de audio/IA pelo painel do Agente WhatsApp, sem exigir edicao direta de variaveis de ambiente para piloto, horario e volume diario.

## Entregue

- Configuracao persistida em `site_config.content.agente_whatsapp_audio_rollout`.
- Fallback preservado para as variaveis `WHATSAPP_AUDIO_ROLLOUT_*`.
- Endpoint `GET /agente-whatsapp/audio/rollout`.
- Endpoint `PUT /agente-whatsapp/audio/rollout`.
- Painel na aba Configuracoes com:
  - modo `all`, `pilot` ou `off`;
  - telefones piloto;
  - janela horaria;
  - limite diario de audio recebido;
  - limite diario de resposta IA;
  - limite diario de TTS;
  - uso diario atual.
- Processamento de STT, resposta IA e TTS passa a respeitar a configuracao persistida.

## Arquivos alterados

- `backend/services/agente_whatsapp_rollout_service.py`
- `backend/routes/agente_whatsapp.py`
- `backend/schemas/agente_whatsapp.py`
- `client/lib/api.ts`
- `client/pages/admin/crm/CrmAgenteWhatsApp.tsx`
- `docs/PLANO_EXECUCAO_WHATSAPP_AUDIO_IA.md`

## Contrato operacional

Campos salvos:

```json
{
  "mode": "pilot",
  "pilot_phones": "5511999999999,5511888888888",
  "hours": "18:00-23:00",
  "daily_input_limit": 20,
  "daily_reply_limit": 10,
  "daily_tts_limit": 10
}
```

Valores de limite `0` significam sem limite diario.

## Criterios de aceite

- Admin altera rollout sem mudar `.env`.
- Modo `off` bloqueia audio/IA automatizado.
- Modo `pilot` restringe aos telefones cadastrados.
- Janela horaria e limites diarios continuam protegendo STT, resposta IA e TTS.
- Readiness continua refletindo o estado efetivo do rollout.

## Rollback

- Definir modo `off` no painel.
- Como contingencia, remover `agente_whatsapp_audio_rollout` do `site_config` para voltar ao fallback por `.env`.

## Fora de escopo

- Segmentacao multiempresa avancada.
- Controle por perfil granular alem do admin autenticado atual.
