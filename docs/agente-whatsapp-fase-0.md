# AGENTE WHATSAPP - Fase 0

Data: 2026-05-13
Status: Fase tecnica documental, sem implementacao funcional

## 1. Objetivo da Fase 0

Esta fase define a arquitetura, os limites tecnicos, os contratos planejados e os riscos do modulo oficial `AGENTE WHATSAPP`.

Nada desta fase deve alterar comportamento de loja, ERP, checkout, pedidos, pagamentos, CRM, marketing, cozinha, logistica, fidelidade ou BI. A entrega e um documento guia para implementar as proximas fases com seguranca.

## 2. Decisao Arquitetural Principal

O `AGENTE WHATSAPP` deve nascer como modulo novo, integrado e progressivo, sem substituir de imediato:

- WhatsApp marketing atual.
- Chatbot/site atual.
- Fluxo atual de cadastro e login.
- Checkout atual.
- Services atuais de pedido, pagamento, cupom, frete e fidelidade.

O modulo deve usar os services existentes como fonte oficial de verdade. A IA nao acessa banco diretamente e nao calcula preco, promocao, frete, pagamento ou status por conta propria.

## 3. Arquitetura Atual Mapeada

### Backend

- Framework: FastAPI.
- ORM: SQLAlchemy.
- Banco: PostgreSQL.
- Migrations: Alembic.
- Entrypoint: `backend/main.py`.
- Services de negocio em `backend/services`.
- Rotas em `backend/routes`.
- Schemas Pydantic em `backend/schemas`.
- Eventos internos em `backend/core/events.py`.

### Frontend

- React 18.
- TypeScript.
- Vite.
- Tailwind.
- Rotas admin em `client/App.tsx`.
- Navegacao admin em `client/config/adminNavigation.ts`.
- Metadados admin em `client/config/adminPageMeta.ts`.
- API client central em `client/lib/api.ts`.

### Modulos ja existentes que serao reaproveitados

- Pedidos: `backend/services/order_service.py`.
- Pagamentos: `backend/services/payment_service.py`.
- Produtos/cardapio: `backend/routes/products.py`.
- Cupons: `backend/services/coupon_service.py`.
- Frete: `backend/services/shipping_service.py`.
- Loja/funcionamento: `backend/routes/store_operation.py`.
- CRM: `backend/routes/crm.py`.
- Eventos de cliente: `backend/routes/customer_events.py`.
- Fidelidade: `backend/services/loyalty_service.py`.
- Logistica: `backend/services/delivery_service.py`.
- Marketing WhatsApp atual: `backend/routes/whatsapp_marketing.py`.
- Chatbot atual: `backend/services/chatbot_service.py`.
- BI: `backend/routes/bi.py`.

## 4. Estado Atual do WhatsApp e Chatbot

### WhatsApp atual

O modulo atual e um disparador/campanhas de WhatsApp:

- Templates.
- Campanhas.
- Listas de contato.
- Configuracao de provedor.
- Envio via Cloud API ou Evolution.
- Webhook de status de mensagem.

Limitacoes para o `AGENTE WHATSAPP`:

- Nao processa mensagens inbound como conversa.
- Nao cria lead automatico por telefone.
- Nao possui sessoes conversacionais WhatsApp.
- Nao possui tool calling.
- Envio em campanha ainda ocorre dentro da request.
- Modelos estao dentro da rota, nao em `backend/models`.

### Chatbot atual

O chatbot/site ja possui:

- Conversas.
- Mensagens.
- Handoff humano.
- Resposta de operador.
- Configuracoes de IA.
- Base de conhecimento.
- Analytics.

Limitacoes para o `AGENTE WHATSAPP`:

- Foco no site, nao no WhatsApp.
- Nao usa telefone como identidade principal.
- Nao possui ferramentas operacionais para criar pedido/pagamento.
- IA atual responde por prompt, sem camada formal de tool calling.

## 5. Principio de Identidade do WhatsApp

No WhatsApp, o telefone e a identidade principal.

Fluxo esperado:

1. Receber mensagem.
2. Normalizar telefone.
3. Buscar cliente por canal WhatsApp ou telefone.
4. Se nao existir, criar lead automaticamente.
5. Criar ou reabrir sessao conversacional.
6. Coletar nome/endereco naturalmente durante a conversa.
7. Criar pedido sem exigir email/senha.
8. Completar cadastro apenas quando fizer sentido.

## 6. Modelo de Cliente Planejado

O sistema atual deve ser preservado. A evolucao deve ser aditiva.

### Nivel 1 - Lead

Criado automaticamente pelo WhatsApp.

Campos minimos:

- telefone.
- origem: whatsapp.
- canal: whatsapp.
- crm_status: lead.
- created_at.

Sem obrigar:

- email.
- senha.
- endereco.

### Nivel 2 - Cliente parcial

Possui:

- telefone.
- nome.
- endereco.
- historico de pedidos.

Pode comprar normalmente pelo WhatsApp.

### Nivel 3 - Cliente completo

Possui:

- email.
- senha.
- conta.
- fidelidade.
- preferencias persistentes.
- autenticacao completa.

## 7. Banco de Dados Planejado

### Tabelas novas do AGENTE WHATSAPP

#### agente_whatsapp_sessions

Responsabilidade: controlar a conversa operacional.

Campos planejados:

- id.
- customer_id nullable.
- phone normalized, indexado.
- provider.
- provider_contact_id nullable.
- status: open, waiting_human, human, ai_paused, closed.
- origin: inbound, campaign, order_status, manual.
- current_intent nullable.
- last_message_at.
- assigned_admin_id nullable.
- ai_enabled boolean.
- automation_blocked boolean.
- metadata_json.
- created_at.
- updated_at.

#### agente_whatsapp_messages

Responsabilidade: historico completo.

Campos planejados:

- id.
- session_id.
- customer_id nullable.
- direction: inbound, outbound.
- sender_type: customer, ai, human, system.
- message_type: text, image, audio, video, document, template, status.
- body.
- media_url nullable.
- provider_message_id nullable.
- provider_status.
- error nullable.
- raw_payload_json.
- created_at.
- delivered_at nullable.
- read_at nullable.

#### agente_whatsapp_events

Responsabilidade: trilha de eventos operacionais e CRM.

Campos planejados:

- id.
- session_id nullable.
- customer_id nullable.
- order_id nullable.
- event_type.
- source.
- payload_json.
- processed_at nullable.
- created_at.

#### agente_whatsapp_context

Responsabilidade: memoria curta/longa e contexto controlado da IA.

Campos planejados:

- id.
- session_id.
- customer_id nullable.
- short_context_json.
- long_context_json.
- preferences_json.
- behavior_json.
- last_intent.
- sentiment nullable.
- updated_at.

#### agente_whatsapp_metrics

Responsabilidade: metricas comerciais e operacionais.

Campos planejados:

- id.
- date.
- sessions_opened.
- messages_inbound.
- messages_outbound.
- ai_responses.
- human_takeovers.
- orders_created.
- revenue.
- avg_response_time_seconds.
- abandoned_sessions.
- recovered_carts.
- created_at.

#### agente_whatsapp_campaigns

Responsabilidade: campanhas proprias do agente.

Campos planejados:

- id.
- name.
- status.
- campaign_type.
- audience_json.
- template_id nullable.
- scheduled_at nullable.
- sent_count.
- delivered_count.
- read_count.
- replied_count.
- conversion_count.
- revenue.
- created_by.
- created_at.
- updated_at.

#### agente_whatsapp_stories

Responsabilidade: stories/status do WhatsApp.

Campos planejados:

- id.
- campaign_id nullable.
- title.
- media_type: image, video.
- media_url.
- caption.
- cta_text nullable.
- cta_url nullable.
- status: draft, scheduled, publishing, published, failed, archived.
- scheduled_at nullable.
- published_at nullable.
- provider_story_id nullable.
- metrics_json.
- created_by.
- created_at.
- updated_at.

### Tabelas de cliente recomendadas

Criar de forma aditiva:

- customer_auth.
- customer_channels.
- customer_preferences.
- customer_message_history.
- customer_behavior.
- customer_ai_context.

O campo `customers.email` nao deve ser alterado de forma brusca na primeira fase. A compatibilidade do login atual deve ser preservada.

## 8. Rotas Planejadas

Prefixo oficial:

- `/api/agente-whatsapp`.

Rotas admin planejadas:

- `GET /api/agente-whatsapp/dashboard`.
- `GET /api/agente-whatsapp/sessions`.
- `GET /api/agente-whatsapp/sessions/{session_id}`.
- `POST /api/agente-whatsapp/sessions/{session_id}/takeover`.
- `POST /api/agente-whatsapp/sessions/{session_id}/return-ai`.
- `POST /api/agente-whatsapp/sessions/{session_id}/pause-ai`.
- `POST /api/agente-whatsapp/sessions/{session_id}/reply`.
- `PATCH /api/agente-whatsapp/sessions/{session_id}/tags`.
- `GET /api/agente-whatsapp/messages`.
- `GET /api/agente-whatsapp/metrics`.
- `GET /api/agente-whatsapp/campaigns`.
- `POST /api/agente-whatsapp/campaigns`.
- `PATCH /api/agente-whatsapp/campaigns/{campaign_id}`.
- `GET /api/agente-whatsapp/stories`.
- `POST /api/agente-whatsapp/stories`.
- `PATCH /api/agente-whatsapp/stories/{story_id}`.

Rotas webhook planejadas:

- `GET /api/agente-whatsapp/webhook/meta`.
- `POST /api/agente-whatsapp/webhook/meta`.
- `POST /api/agente-whatsapp/webhook/evolution`.

As ferramentas internas da IA nao devem ser expostas como endpoints publicos sem necessidade. Devem ser services internos com schemas fortes.

## 9. Permissoes Planejadas

Permissoes oficiais:

- `agente_whatsapp_view`.
- `agente_whatsapp_manage`.
- `agente_whatsapp_takeover`.
- `agente_whatsapp_campaigns`.

Modulo no admin:

CRM

- Dashboard CRM.
- Clientes.
- Inteligencia de Clientes.
- Pipeline.
- Grupos & Segmentacoes.
- Tarefas.
- Agente WhatsApp.

## 10. Eventos Planejados

### Eventos de conversa

- agente_whatsapp_message_received.
- agente_whatsapp_message_sent.
- agente_whatsapp_session_started.
- agente_whatsapp_session_closed.
- agente_whatsapp_human_takeover_started.
- agente_whatsapp_human_takeover_finished.
- agente_whatsapp_ai_paused.
- agente_whatsapp_ai_resumed.
- agente_whatsapp_intent_detected.
- agente_whatsapp_cart_abandoned.
- agente_whatsapp_order_intent_confirmed.

### Eventos obrigatorios de pedido

Mapear eventos existentes e padronizar para:

- order_created.
- payment_approved.
- order_preparing.
- order_ready.
- order_out_delivery.
- order_delivered.
- order_cancelled.

Esses eventos devem alimentar:

- mensagens de status.
- CRM.
- automacoes.
- metricas.
- BI.
- historico do cliente.

## 11. Filas e Workers Planejados

Dependencia alvo: Redis.

Filas planejadas:

- agente_whatsapp_inbound.
- agente_whatsapp_ai.
- agente_whatsapp_outbound.
- agente_whatsapp_status.
- agente_whatsapp_campaigns.
- agente_whatsapp_stories.
- agente_whatsapp_metrics.

Workers planejados:

- InboundMessageWorker.
- AIOrchestratorWorker.
- OutboundMessageWorker.
- OrderStatusNotificationWorker.
- CampaignDispatchWorker.
- StoryPublisherWorker.
- MetricsAggregationWorker.

Regras obrigatorias:

- Toda mensagem deve ter idempotency key.
- Webhook deve aceitar duplicidade sem duplicar conversa.
- Falhas devem ter retry com limite.
- Erros definitivos devem ficar auditaveis.
- Nenhuma request admin deve ficar travada aguardando lote de mensagens.

## 12. Tool Calling Planejado

A IA so pode operar por ferramentas reais.

Ferramentas iniciais:

- buscar_cliente_por_telefone.
- criar_lead_por_telefone.
- atualizar_dados_cliente.
- buscar_produtos.
- buscar_produto_por_nome.
- buscar_tamanhos_produto.
- buscar_massas_bordas_adicionais.
- buscar_promocoes.
- calcular_preco_item.
- calcular_frete.
- validar_cupom.
- criar_pedido.
- consultar_pedido.
- atualizar_pedido.
- cancelar_pedido.
- gerar_pagamento_pix.
- gerar_link_pagamento.
- consultar_pagamento.
- consultar_status_pedido.
- buscar_enderecos_cliente.
- salvar_endereco_cliente.
- buscar_ultimo_pedido.
- repetir_pedido.
- buscar_fidelidade.
- salvar_preferencia.

Regra critica:

A IA nao pode inventar preco, promocao, pedido, status, pagamento, prazo de entrega ou disponibilidade.

## 13. Feature Flags Planejadas

O modulo deve ser ativado progressivamente.

Flags sugeridas:

- agente_whatsapp_enabled.
- agente_whatsapp_inbound_enabled.
- agente_whatsapp_ai_enabled.
- agente_whatsapp_order_creation_enabled.
- agente_whatsapp_payment_enabled.
- agente_whatsapp_status_notifications_enabled.
- agente_whatsapp_campaigns_enabled.
- agente_whatsapp_stories_enabled.
- agente_whatsapp_human_takeover_enabled.

## 14. Matriz de Integracao

| Modulo | Integracao com AGENTE WHATSAPP | Estrategia segura |
| --- | --- | --- |
| Clientes | Criar lead por telefone e completar perfil | Aditivo, sem quebrar login atual |
| Pedidos | Criar/consultar/alterar via OrderService | Nunca escrever direto no banco |
| Pagamentos | Gerar Pix/link/status via PaymentService | Reaproveitar webhook atual |
| Produtos | Consultar cardapio e precos oficiais | Usar rotas/services atuais |
| Cupons | Validar cupom oficial | Usar CouponService |
| Frete | Calcular disponibilidade e valor | Usar ShippingService |
| Cozinha | Receber pedido criado normalmente | Sem mudanca inicial |
| Logistica | Status de entrega e saiu para entrega | Usar DeliveryService/eventos |
| CRM | Historico, tags, eventos e comportamento | Sincronizar por eventos |
| Fidelidade | Pontos e beneficios | Usar LoyaltyService |
| Marketing | Campanhas e recompra | Integrar sem remover disparador atual |
| BI | Metricas WhatsApp e conversao | Agregar eventos e pedidos |

## 15. Matriz de Risco

| Risco | Impacto | Mitigacao |
| --- | --- | --- |
| Quebrar login atual ao mexer em customers.email | Alto | Criar customer_auth/customer_channels antes de mudar constraints |
| Duplicar clientes por telefone com formatos diferentes | Alto | Normalizacao de telefone e indice unico por canal |
| IA criar pedido com preco errado | Critico | Tool calling por services oficiais |
| Webhook duplicar mensagens | Alto | Idempotencia por provider_message_id e payload hash |
| Envio em massa travar API | Alto | Redis + worker outbound |
| Realtime instavel no painel | Medio | Implementar canal dedicado apos persistencia |
| Story nao suportado pelo provedor | Medio | Isolar provider adapter e indicar suporte por conexao |
| Campanha sem consentimento | Alto | Respeitar LGPD e marketing_whatsapp_consent |
| Loop de IA/automacao | Critico | Rate limit, automation_blocked e guardrails por sessao |

## 16. Ordem Segura das Proximas Fases

1. Fase 1: base de identidade do cliente.
2. Fase 2: tabelas e rotas base do AGENTE WHATSAPP.
3. Fase 3: webhook inbound com criacao de lead.
4. Fase 4: tool calling operacional.
5. Fase 5: criacao de pedidos pelo WhatsApp.
6. Fase 6: status automatico de pedidos.
7. Fase 7: central operacional.
8. Fase 8: Redis, workers e outbox.
9. Fase 9: CRM conversacional.
10. Fase 10: campanhas e retencao.
11. Fase 11: stories WhatsApp.
12. Fase 12: observabilidade e hardening final.

## 17. Criterios de Aceite da Fase 0

- Documento de arquitetura criado.
- Nenhuma funcionalidade atual alterada.
- Nenhuma migration criada nesta fase.
- Nenhuma rota nova criada nesta fase.
- Nenhum componente frontend criado nesta fase.
- Riscos e dependencias registrados.
- Plano de fases pronto para acompanhamento.

## 18. Criterios de Aceite da Fase 1

A Fase 1 so deve ser iniciada quando estes pontos forem aceitos:

- Lead por telefone nao pode quebrar login atual.
- Cliente completo continua usando email/senha.
- Cliente parcial pode existir sem senha.
- WhatsApp usa telefone como identidade principal.
- Duplicidade por telefone deve ser evitada.
- Checkout, conta, CRM e pedidos devem continuar funcionando.

## 19. Validacao Requerida por Fase

Validacoes minimas apos cada fase com codigo:

- `npm.cmd run typecheck`.
- `npm.cmd test`.
- `npm.cmd run build`.
- Smoke test manual de login.
- Smoke test manual de checkout.
- Smoke test manual de pedidos/admin.
- Smoke test manual de CRM/clientes.
- Smoke test manual de WhatsApp atual quando a fase tocar marketing/WhatsApp.

## 20. Decisao Final da Fase 0

O `AGENTE WHATSAPP` deve ser implementado como evolucao modular e aditiva.

Nao deve ser um MVP paralelo.
Nao deve substituir o WhatsApp marketing atual no inicio.
Nao deve substituir o chatbot/site atual no inicio.
Nao deve alterar a arquitetura de pedidos/pagamentos.

O primeiro codigo seguro a implementar na Fase 1 e a separacao de identidade/autenticacao/canal, preservando compatibilidade total com o sistema atual.
