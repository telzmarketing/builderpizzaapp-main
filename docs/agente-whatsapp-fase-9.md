# AGENTE WHATSAPP - Fase 9

## Objetivo

Ativar processamento automatico da outbox criada na Fase 8, com controle operacional e metricas basicas para acompanhamento.

## Entrega

- Criado worker de background em `backend/services/agente_whatsapp_worker.py`.
- Worker iniciado no lifespan do FastAPI quando `AGENTE_WHATSAPP_WORKER_ENABLED=true`.
- Configuracoes adicionadas:
  - `AGENTE_WHATSAPP_WORKER_ENABLED`
  - `AGENTE_WHATSAPP_WORKER_INTERVAL_SECONDS`
  - `AGENTE_WHATSAPP_WORKER_BATCH_SIZE`
- O worker processa mensagens pendentes por lote e intervalo configuraveis.
- O processamento da outbox usa trava de linha (`FOR UPDATE SKIP LOCKED`) para reduzir risco de envio duplicado em ambiente com mais de uma instancia.
- Adicionado endpoint de metricas:
  - `GET /api/agente-whatsapp/outbox/metrics`
- A central CRM do AGENTE WHATSAPP passa a exibir latencia media de envio.

## Observabilidade

O endpoint de metricas retorna:

- totais por status da fila
- mensagens `queued` ainda sem item na outbox
- idade da pendencia mais antiga
- latencia media dos ultimos envios
- data do ultimo envio
- data e descricao do ultimo erro

## Decisao tecnica

Nao foi introduzida dependencia nova de Redis nesta fase porque o projeto atual ainda nao possui Redis configurado como dependencia operacional. A fila usa PostgreSQL outbox, que ja existe no projeto e permite ativar o worker sem criar infraestrutura paralela.

## Proxima fase sugerida

Fase 10: painel de auditoria da outbox com filtros, detalhe de erro, reprocessamento seletivo e alerta visual para itens `dead`.
