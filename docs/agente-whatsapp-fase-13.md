# AGENTE WHATSAPP - Fase 13

## Objetivo

Adicionar observabilidade operacional ao AGENTE WHATSAPP para acompanhar saude, fila, providers, erros recentes e historico de alertas.

## Entrega

- Criado endpoint agregado de observabilidade.
- A observabilidade reaproveita outbox, provider states e alertas internos ja existentes.
- O painel do AGENTE WHATSAPP passa a exibir:
  - saude operacional
  - taxa de sucesso de envio
  - quantidade de alertas ativos
  - providers pausados
  - item pendente mais antigo
  - entregas tentadas
  - tabela de providers com sucesso, falhas e latencia
  - erros recentes
  - historico de alertas internos

## Endpoints

- `GET /api/agente-whatsapp/observability`

## Regras

- Status `critical` quando houver provider pausado, item morto ou alerta critico ativo.
- Status `degraded` quando houver falhas ou item pendente antigo.
- Status `healthy` quando nao houver condicao operacional de risco.
- Nenhuma tabela nova foi criada nesta fase.

## Proxima fase sugerida

Fase 14: campanhas WhatsApp completas, com publico, templates, agendamento, fila de envio e metricas por campanha.
