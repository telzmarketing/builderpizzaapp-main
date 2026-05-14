# AGENTE WHATSAPP - Fase 12

## Objetivo

Criar notificacoes internas para administradores quando a operacao do AGENTE WHATSAPP exigir atencao.

## Entrega

- Criada a tabela `agente_whatsapp_internal_alerts`.
- Criado mecanismo de deduplicacao por `dedupe_key`.
- Alertas sao sincronizados automaticamente pela outbox e pelo worker.
- Alertas ativos sao resolvidos automaticamente quando a condicao deixa de existir.
- Alertas reconhecidos pelo administrador deixam de aparecer no sino, mas continuam historicos ate serem resolvidos.
- O sino global do painel administrativo passa a exibir alertas criticos do AGENTE WHATSAPP.
- Ao clicar no alerta do sino, o administrador e levado para `/painel/crm/agente-whatsapp`.

## Condicoes monitoradas

- Provider pausado.
- Itens `dead` ha mais de X minutos.
- Item pendente ha mais de 15 minutos.

## Configuracoes

- `AGENTE_WHATSAPP_DEAD_ALERT_AFTER_MINUTES`: tempo minimo para considerar item `dead` como alerta interno.

## Endpoints

- `GET /api/agente-whatsapp/outbox/alerts`
- `GET /api/agente-whatsapp/outbox/internal-alerts`
- `POST /api/agente-whatsapp/outbox/internal-alerts/{alert_id}/ack`

## Banco

Migration adicionada:

- `backend/migrations/versions/20260514_agente_whatsapp_internal_alerts.py`

O bootstrap runtime em `backend/main.py` tambem cria a tabela e indices para ambientes que dependem das migrations idempotentes no startup.

## Proxima fase sugerida

Fase 13: painel de observabilidade do AGENTE WHATSAPP com historico de alertas, taxa de sucesso da outbox, falhas por provider e tempo medio de entrega.
