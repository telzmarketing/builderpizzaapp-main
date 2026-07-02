# Agente WhatsApp Audio IA - Fase 11

Data: 2026-07-01

Status: executada funcionalmente no sistema.

## 1. Objetivo

Permitir expansao gradual do Audio/IA por piloto, horario e volume diario, sem liberar o recurso para todos os clientes de uma vez.

## 2. Escopo entregue

- Novo service `AgenteWhatsAppRolloutService`.
- Configuracoes por env para modo de rollout, telefones piloto, janela horaria e limites diarios.
- STT respeitando rollout antes de enfileirar/processar audio.
- Resposta automatica respeitando rollout antes de responder.
- TTS respeitando rollout antes de gerar voz.
- Readiness operacional exibindo status, limites e uso diario do rollout.
- Plano principal atualizado com Fase 11.

## 3. Arquivos alterados

- `backend/config.py`
- `backend/routes/agente_whatsapp.py`
- `backend/services/agente_whatsapp_processing_service.py`
- `backend/services/agente_whatsapp_rollout_service.py`
- `docs/PLANO_EXECUCAO_WHATSAPP_AUDIO_IA.md`

## 4. Variaveis de configuracao

```env
WHATSAPP_AUDIO_ROLLOUT_MODE=all
WHATSAPP_AUDIO_ROLLOUT_PILOT_PHONES=
WHATSAPP_AUDIO_ROLLOUT_HOURS=
WHATSAPP_AUDIO_ROLLOUT_DAILY_INPUT_LIMIT=0
WHATSAPP_AUDIO_ROLLOUT_DAILY_REPLY_LIMIT=0
WHATSAPP_AUDIO_ROLLOUT_DAILY_TTS_LIMIT=0
```

Modos:

- `all`: comportamento atual, sem restringir por telefone.
- `pilot`: permite apenas telefones listados em `WHATSAPP_AUDIO_ROLLOUT_PILOT_PHONES`.
- `off`: bloqueia o rollout de audio.

`WHATSAPP_AUDIO_ROLLOUT_HOURS` aceita uma ou mais janelas:

```env
WHATSAPP_AUDIO_ROLLOUT_HOURS=18:00-23:00,10:00-14:00
```

Limite `0` significa sem limite diario.

## 5. Recomendacao para piloto real

```env
WHATSAPP_AUDIO_ROLLOUT_MODE=pilot
WHATSAPP_AUDIO_ROLLOUT_PILOT_PHONES=5511999999999,5511888888888
WHATSAPP_AUDIO_ROLLOUT_HOURS=18:00-23:00
WHATSAPP_AUDIO_ROLLOUT_DAILY_INPUT_LIMIT=50
WHATSAPP_AUDIO_ROLLOUT_DAILY_REPLY_LIMIT=20
WHATSAPP_AUDIO_ROLLOUT_DAILY_TTS_LIMIT=10
```

## 6. Criterios de aceite

- Telefone fora do piloto nao dispara STT/resposta/voz quando modo `pilot`.
- Fora da janela horaria, o sistema nao avanca processamento de audio.
- Limites diarios impedem crescimento inesperado de custo.
- Texto, atendimento humano, pedidos, checkout, Marketing e Gateway continuam sem alteracao.

## 7. Rollback

Para interromper expansao gradual sem desligar todo o modulo:

```env
WHATSAPP_AUDIO_ROLLOUT_MODE=off
```

Para voltar ao comportamento aberto:

```env
WHATSAPP_AUDIO_ROLLOUT_MODE=all
```

## 8. Fora do escopo

- Tela administrativa para editar rollout.
- Segmentacao por loja/tenant com UI propria.
- Limite financeiro com billing real de provedor.
