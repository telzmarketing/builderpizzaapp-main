# AGENTE WHATSAPP - Fase 11

## Objetivo

Adicionar alertas operacionais e politica de escalonamento para a outbox do AGENTE WHATSAPP.

## Entrega

- Criada a tabela `agente_whatsapp_provider_states`.
- Criado controle por provider do AGENTE WHATSAPP, separado do modulo WhatsApp Marketing.
- Providers passam a ter:
  - status `active` ou `paused`
  - contador de falhas consecutivas
  - limite de falhas
  - ultimo sucesso
  - ultima falha
  - motivo da pausa
  - horario de retomada automatica
- O worker da outbox passa a consultar o estado do provider antes de enviar.
- Apos falhas consecutivas acima do limite configurado, o provider e pausado temporariamente.
- Itens nao sao enviados enquanto o provider esta pausado; eles ficam reagendados para a retomada.
- O painel permite pausar e retomar provider manualmente.
- O painel exibe alertas operacionais para:
  - itens `dead`
  - pendencias antigas
  - provider pausado

## Configuracoes

- `AGENTE_WHATSAPP_PROVIDER_FAILURE_THRESHOLD`: quantidade de falhas consecutivas antes de pausar o provider.
- `AGENTE_WHATSAPP_PROVIDER_PAUSE_MINUTES`: tempo de pausa automatica em minutos.

## Endpoints

- `GET /api/agente-whatsapp/outbox/alerts`
- `GET /api/agente-whatsapp/outbox/providers`
- `POST /api/agente-whatsapp/outbox/providers/{provider}/pause`
- `POST /api/agente-whatsapp/outbox/providers/{provider}/resume`

## Banco

Migration adicionada:

- `backend/migrations/versions/20260514_agente_whatsapp_provider_states.py`

O bootstrap runtime em `backend/main.py` tambem cria a tabela e indices para ambientes que dependem das migrations idempotentes no startup.

## Proxima fase sugerida

Fase 12: notificacoes internas para administradores quando provider pausar ou quando a fila tiver itens `dead` por mais de X minutos.
