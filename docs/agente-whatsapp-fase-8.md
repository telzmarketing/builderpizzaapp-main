# AGENTE WHATSAPP - Fase 8

## Objetivo

Adicionar a camada operacional de fila/outbox para enviar mensagens `queued` do AGENTE WHATSAPP sem criar um sistema paralelo de disparo.

## Entrega

- Criada a tabela `agente_whatsapp_outbox`.
- Criado o service `AgenteWhatsAppOutboxService`.
- Mensagens outbound com `provider_status = queued` viram itens idempotentes de outbox.
- Cada mensagem tem uma unica chave `agente_whatsapp:{message_id}`.
- O worker processa tentativas, registra erro, respeita `max_attempts` e move itens para `dead` apos esgotar retries.
- Reaproveitado o sender existente do modulo WhatsApp Marketing:
  - WhatsApp Cloud API (`official`)
  - Evolution API (`evolution`)
- Adicionados endpoints administrativos:
  - `GET /api/agente-whatsapp/outbox/summary`
  - `GET /api/agente-whatsapp/outbox`
  - `POST /api/agente-whatsapp/outbox/enqueue`
  - `POST /api/agente-whatsapp/outbox/process`
  - `POST /api/agente-whatsapp/outbox/{id}/retry`
- A central CRM do AGENTE WHATSAPP agora mostra resumo da fila e pode processar a fila manualmente.

## Regras de seguranca operacional

- A rota publica de webhook continua separada das rotas administrativas.
- O envio externo so acontece pela fila.
- Uma mensagem `queued` nao gera duplicidade porque `message_id` e `idempotency_key` sao unicos.
- Falhas de provider ficam registradas em `agente_whatsapp_outbox.error` e na mensagem relacionada.
- O provider `qr` permanece bloqueado porque ainda nao existe servico de sessao QR ativo.

## Limites desta fase

- Esta fase entrega a outbox pronta para worker.
- Redis/background worker dedicado ainda nao foi introduzido para evitar mudanca estrutural maior sem necessidade imediata.
- O processamento pode ser acionado pelo endpoint administrativo ou por um job externo chamando `POST /api/agente-whatsapp/outbox/process`.

## Proxima fase sugerida

Fase 9: worker assincrono/daemon com Redis ou scheduler, observabilidade de envio, metricas de latencia e alarmes para mensagens em `dead`.
