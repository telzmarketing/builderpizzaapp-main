# Auditoria - Trilha AGENTE WHATSAPP Fases 0 a 19

Data: 2026-07-01

## Objetivo

Classificar a trilha historica `docs/agente-whatsapp-fase-0.md` ate `docs/agente-whatsapp-fase-19.md` contra o codigo real atual, separando o que e base funcional, o que ja foi implementado, o que foi absorvido pelo plano de Audio/IA e o que deve ser tratado como legado ou opcional.

Esta auditoria nao altera comportamento do sistema.

## Conclusao executiva

A trilha ate a fase 19 e util como base historica e checklist do modulo AGENTE WHATSAPP geral, mas nao deve ser executada novamente como se fosse pendencia linear.

O codigo atual ja contem a maior parte do que essas fases descrevem:

- identidade por telefone e canais de cliente;
- nucleo de sessoes e mensagens do Agente WhatsApp;
- webhooks inbound Meta/Evolution/Baileys;
- tools do ERP;
- venda assistida;
- status de pedido;
- painel CRM do Agente;
- outbox, worker, auditoria, alertas internos e observabilidade;
- campanhas, stories e automacoes internas;
- IA, guardrails e configuracao propria de provider/prompt;
- extensoes novas de Audio/IA executadas no plano separado `PLANO_EXECUCAO_WHATSAPP_AUDIO_IA.md`.

## Decisao recomendada

Nao continuar executando as fases 0 a 19 como proximas fases.

Usar esta trilha assim:

- Fases 0 a 13: base funcional do Agente WhatsApp geral, ja aproveitada pelo Audio/IA.
- Fases 14 a 16: funcionalidades existentes, mas devem ser tratadas com cuidado porque campanhas, stories e automacoes tambem existem em Marketing/CRM; qualquer evolucao deve evitar duplicacao.
- Fases 17 a 19: base da IA do Agente, necessaria e aproveitada pelo Audio/IA.
- Plano de Audio/IA: segue como trilha propria ja executada ate a Fase 12.

## Classificacao fase a fase

| Fase | Tema | Status no codigo real | Precisamos dela daqui para frente? | Decisao |
|---:|---|---|---|---|
| 0 | Arquitetura e contratos | Concluida como documento base. | Sim, como referencia historica. | Manter, nao executar. |
| 1 | Identidade por telefone | Concluida. Ha `customer_auth`, `customer_channels`, `customer_preferences` e `CustomerIdentityService`. | Sim, e base obrigatoria. | Manter. |
| 2 | Nucleo Agente WhatsApp | Concluida. Ha models, rotas, schemas e tabelas principais do Agente. | Sim, e base obrigatoria. | Manter. |
| 3 | Webhooks inbound | Concluida e ampliada depois pelo Gateway/Audio. | Sim, e base obrigatoria. | Manter. |
| 4 | Tool calling ERP | Concluida. `AgenteWhatsAppToolService` consulta services reais. | Sim, e base da IA segura. | Manter. |
| 5 | Venda assistida | Concluida. Usa `OrderService.quote_checkout` e tools de pedido/frete/cupom/fidelidade. | Sim, com guardrails. | Manter com cautela. |
| 6 | Status de pedido | Concluida. `AgenteWhatsAppStatusService` esta ligado a eventos do ERP. | Sim, util para atendimento e pos-venda. | Manter. |
| 7 | Painel CRM | Concluida. Rota `/painel/crm/agente-whatsapp` existe. | Sim. | Manter. |
| 8 | Outbox | Concluida. `AgenteWhatsAppOutboxService` e tabela de outbox existem. | Sim, obrigatoria para envio seguro. | Manter. |
| 9 | Worker da outbox | Concluida. Worker inicia via `AGENTE_WHATSAPP_WORKER_ENABLED`. | Sim. | Manter. |
| 10 | Auditoria da outbox | Concluida. Painel lista fila, status, retry e detalhes. | Sim, operacional. | Manter. |
| 11 | Provider states/escalonamento | Concluida. Ha `agente_whatsapp_provider_states` e pausa/resume. | Sim, operacional. | Manter. |
| 12 | Alertas internos | Concluida. Ha `agente_whatsapp_internal_alerts` e endpoints de alerta. | Sim, operacional. | Manter. |
| 13 | Observabilidade | Concluida. Ha endpoint e bloco de observabilidade no painel. | Sim, operacional. | Manter. |
| 14 | Campanhas internas do Agente | Implementada, mas sobrepoe parcialmente Marketing WhatsApp. | Sim somente se for fluxo do Agente; nao expandir sem decisao. | Tratar como legado/controlado. |
| 15 | Stories/Status WhatsApp | Implementada, mas e opcional e depende do provider. | Opcional. | Manter sem expandir ate piloto pedir. |
| 16 | Automacoes comerciais | Implementada. Tem recompra, reativacao, carrinho, aniversario e fidelidade. | Sim, mas deve evitar conflito com Marketing/CRM. | Usar com guardrails. |
| 17 | IA vendedora | Concluida. `AgenteWhatsAppAIService` existe e usa tools reais. | Sim, base do atendimento inteligente. | Manter. |
| 18 | Guardrails IA | Concluida. Bloqueia loops, humano, IA pausada e duplicidade. | Sim, obrigatoria. | Manter. |
| 19 | Config propria da IA | Concluida. `agente_whatsapp_ai_settings` e endpoints existem. | Sim, obrigatoria. | Manter. |

## Evidencias no codigo atual

Backend:

- `backend/models/customer_identity.py`: identidade por telefone e canais.
- `backend/services/customer_identity_service.py`: normalizacao, busca e criacao de lead WhatsApp.
- `backend/models/agente_whatsapp.py`: sessoes, mensagens, IA, outbox, provider states, alertas, campanhas, stories, audio e jobs.
- `backend/routes/agente_whatsapp.py`: rotas do Agente, webhooks, tools, IA, audio, outbox, observabilidade, campanhas, stories e automacoes.
- `backend/services/agente_whatsapp_service.py`: dashboard, conversas, webhooks, campanhas, stories e automacoes.
- `backend/services/agente_whatsapp_ai_service.py`: IA, provider settings e guardrails.
- `backend/services/agente_whatsapp_tools.py`: ferramentas reais do ERP.
- `backend/services/agente_whatsapp_outbox_service.py`: fila, provider states, alertas e observabilidade.
- `backend/services/agente_whatsapp_worker.py`: processamento background.
- `backend/services/agente_whatsapp_status_service.py`: eventos de status de pedido.
- `backend/main.py`: registro de rotas, startup do worker e handlers de eventos.

Frontend:

- `client/App.tsx`: rota `/painel/crm/agente-whatsapp`.
- `client/config/adminNavigation.ts`: item `Agente WhatsApp` no CRM.
- `client/config/adminPageMeta.ts`: metadados da pagina.
- `client/pages/admin/crm/CrmAgenteWhatsApp.tsx`: conversas, configuracoes, IA, audio, outbox, observabilidade, campanhas, stories, automacoes e avisos de pedido.
- `client/lib/api.ts`: contratos do Agente WhatsApp.

Migrations relevantes:

- `20260513_customer_identity_channels.py`
- `20260513_agente_whatsapp_core.py`
- `20260513_agente_whatsapp_inbound_webhooks.py`
- `20260513_agente_whatsapp_tools.py`
- `20260513_agente_whatsapp_outbox.py`
- `20260514_agente_whatsapp_provider_states.py`
- `20260514_agente_whatsapp_internal_alerts.py`
- `20260514_agente_whatsapp_ai_settings.py`
- `20260701_whatsapp_audio_phase1_deliveries.py`
- `20260701_whatsapp_audio_phase2_inbound_jobs.py`
- `20260701_whatsapp_audio_phase3_audio_stt.py`
- `20260701_whatsapp_audio_phase5_agent_response.py`

## Pontos de atencao

1. Campanhas e Stories dentro do Agente podem duplicar responsabilidades do modulo Marketing.
   - Decisao segura: nao evoluir Fases 14 e 15 sem uma decisao de produto clara.

2. Automacoes comerciais podem cruzar com Marketing/CRM.
   - Decisao segura: manter guardrails e revisar antes de ativar em massa.

3. O plano de Audio/IA ja expandiu a trilha geral.
   - Decisao segura: tratar `PLANO_EXECUCAO_WHATSAPP_AUDIO_IA.md` como plano especifico e nao misturar suas fases com `agente-whatsapp-fase-*.md`.

4. A UI do Agente esta funcional, mas acumula historico de varias fases.
   - Decisao segura: qualquer limpeza visual deve ser uma tarefa separada, com criterio de aceite proprio.

## Proxima acao recomendada

Encerrar a trilha 0-19 como backlog executado/historico e seguir para uma destas opcoes:

1. Publicar as alteracoes atuais com commit/push.
2. Validar deploy na VPS.
3. Fazer uma limpeza documental para marcar explicitamente `agente-whatsapp-fase-0..19` como trilha historica.
4. Planejar um ajuste de produto para decidir se campanhas/stories/automacoes devem permanecer no Agente ou ficar somente em Marketing.
