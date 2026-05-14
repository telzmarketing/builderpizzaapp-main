# AGENTE WHATSAPP - Fase 14

## Objetivo

Adicionar campanhas WhatsApp com publico, template, agendamento, fila de envio e metricas por campanha.

## Entrega

- Criado fluxo de campanhas usando a tabela `agente_whatsapp_campaigns`.
- Campanhas armazenam publico e template em `audience_json`.
- Publicos suportados:
  - lista manual de telefones
  - clientes com consentimento WhatsApp
  - leads WhatsApp
- Templates rapidos disponiveis no backend e no painel.
- Disparo cria sessoes quando necessario e registra mensagens outbound com `provider_status = queued`.
- A outbox oficial do AGENTE WHATSAPP assume o envio.
- Campanhas agendadas sao processadas pelo worker e tambem podem ser processadas manualmente no painel.
- Painel mostra campanhas, status, publico, agendamento e metricas basicas da fila por campanha.

## Endpoints

- `GET /api/agente-whatsapp/campaigns/templates`
- `GET /api/agente-whatsapp/campaigns`
- `POST /api/agente-whatsapp/campaigns`
- `POST /api/agente-whatsapp/campaigns/{campaign_id}/dispatch`
- `POST /api/agente-whatsapp/campaigns/process-scheduled`

## Regras

- Campanha manual exige pelo menos um telefone.
- Telefones sao normalizados e deduplicados antes do envio.
- Campanha agendada nao dispara antes de `scheduled_at`, exceto quando o admin usa disparo forcado.
- O mesmo telefone nao recebe a mesma campanha duas vezes.
- Variaveis suportadas no template:
  - `{{nome}}`
  - `{{primeiro_nome}}`
  - `{{telefone}}`

## Proxima fase sugerida

Fase 15: Stories/Status WhatsApp com upload/agendamento, biblioteca de midias, CTA e metricas.
