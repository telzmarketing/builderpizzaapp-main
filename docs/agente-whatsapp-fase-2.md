# AGENTE WHATSAPP - Fase 2

Data: 2026-05-13
Status: Implementacao do nucleo base do modulo

## Objetivo

Criar a estrutura central do `AGENTE WHATSAPP` sem ativar conversa automatica, webhook inbound, IA, pedidos pelo WhatsApp ou campanhas operacionais.

## Escopo implementado

- Tabelas oficiais do modulo:
  - `agente_whatsapp_sessions`
  - `agente_whatsapp_messages`
  - `agente_whatsapp_events`
  - `agente_whatsapp_context`
  - `agente_whatsapp_metrics`
  - `agente_whatsapp_campaigns`
  - `agente_whatsapp_stories`
- Models SQLAlchemy em `backend/models/agente_whatsapp.py`.
- Schemas Pydantic em `backend/schemas/agente_whatsapp.py`.
- Service em `backend/services/agente_whatsapp_service.py`.
- Migration Alembic `20260513_agente_whatsapp_core`.
- Runtime schema em `backend/main.py`.
- Rotas admin base em `/api/agente-whatsapp`.
- API client tipada em `client/lib/api.ts`.

## Rotas adicionadas

- `GET /api/agente-whatsapp/dashboard`
- `GET /api/agente-whatsapp/sessions`
- `POST /api/agente-whatsapp/sessions`
- `GET /api/agente-whatsapp/sessions/{session_id}`
- `PATCH /api/agente-whatsapp/sessions/{session_id}`
- `GET /api/agente-whatsapp/sessions/{session_id}/messages`
- `POST /api/agente-whatsapp/sessions/{session_id}/messages`

## Regras preservadas

- O WhatsApp marketing atual nao foi removido nem substituido.
- O chatbot/site atual nao foi removido nem substituido.
- Nenhum pedido e criado nesta fase.
- Nenhum pagamento e gerado nesta fase.
- Nenhuma IA conversa com cliente nesta fase.
- Toda rota nova e administrativa.

## Integracao com a Fase 1

Ao criar uma sessao por telefone, o service usa a base de identidade da Fase 1:

- procura cliente pelo canal WhatsApp/telefone;
- cria lead WhatsApp se ainda nao existir;
- evita duplicar clientes quando ja ha telefone vinculado;
- cria contexto inicial da sessao.

## Fora de escopo

- Webhook publico do WhatsApp.
- Processamento de mensagens inbound reais.
- Tool calling.
- Criacao de pedido.
- Envio via provider.
- Redis/workers/outbox.
- Painel visual da central operacional.
- Stories publicados em provider real.

## Criterios de aceite

- Models, migrations e runtime schema existem.
- Rotas `/api/agente-whatsapp` carregam no backend.
- Criacao de sessao nao altera pedido, pagamento ou campanha atual.
- Mensagem registrada gera evento interno do modulo.
- Build e testes do frontend continuam passando.
