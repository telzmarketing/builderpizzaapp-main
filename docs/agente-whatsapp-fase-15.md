# AGENTE WHATSAPP - Fase 15

## Objetivo

Adicionar Stories/Status WhatsApp com upload de imagem/video, CTA, agendamento, biblioteca e metricas basicas.

## Entrega

- Criado fluxo de stories usando a tabela `agente_whatsapp_stories`.
- O painel permite criar stories com:
  - titulo
  - imagem ou video
  - legenda
  - CTA
  - link do CTA
  - campanha vinculada
  - agendamento
- Upload real reaproveitando o endpoint `/admin/upload`.
- Biblioteca visual de stories salvos no painel.
- Templates rapidos de stories.
- Publicacao manual ou forcada.
- Processamento automatico de stories agendados pelo worker.
- Metricas locais basicas no `metrics_json`.

## Endpoints

- `GET /api/agente-whatsapp/stories/templates`
- `GET /api/agente-whatsapp/stories`
- `POST /api/agente-whatsapp/stories`
- `PATCH /api/agente-whatsapp/stories/{story_id}`
- `POST /api/agente-whatsapp/stories/{story_id}/publish`
- `POST /api/agente-whatsapp/stories/process-scheduled`

## Regras

- Story exige titulo, tipo de midia e URL de midia.
- Midias sao enviadas pelo upload administrativo existente.
- Story agendado nao publica antes de `scheduled_at`, exceto com publicacao forcada.
- A publicacao nesta fase registra o status internamente e nao inventa metricas externas do WhatsApp.

## Proxima fase sugerida

Fase 16: automacoes comerciais do AGENTE WHATSAPP para recompra, carrinho abandonado, aniversario, fidelidade e reativacao.
