# Agente WhatsApp Audio IA - Fase 8

Data: 2026-07-01

Status: executada funcionalmente no sistema.

## 1. Objetivo

Medir a operacao e o resultado comercial do audio por IA no Agente WhatsApp, cobrindo STT, TTS, jobs, custo estimado e conversoes por campanha.

## 2. Escopo entregue

- Novo service `AgenteWhatsAppAnalyticsService`.
- Endpoint de metricas de audio.
- Indicadores de STT: sucesso, baixa confianca, falha e latencia media quando disponivel.
- Indicadores de TTS: audios gerados, falhas e latencia media.
- Indicadores de jobs por tipo/status.
- Estimativa operacional de custo STT/TTS.
- Conversoes atribuidas por campanha em janela de 7 dias.
- Receita atribuida por pedidos de clientes vinculados a campanhas.
- Painel do Agente com cards de audio, custo e pedidos atribuidos.
- Tabela de campanhas com mensagens, clientes, pedidos, receita e taxa de conversao.
- Registro de latencia STT em `transcription_quality_json` para novos audios.
- Contrato Pydantic aninhado para impedir regressao silenciosa no endpoint.
- Aviso visual no painel quando as metricas de audio nao carregarem.

## 3. Arquivos alterados

- `backend/routes/agente_whatsapp.py`
- `backend/schemas/agente_whatsapp.py`
- `backend/services/agente_whatsapp_analytics_service.py`
- `backend/services/agente_whatsapp_audio_service.py`
- `client/lib/api.ts`
- `client/pages/admin/crm/CrmAgenteWhatsApp.tsx`
- `docs/PLANO_EXECUCAO_WHATSAPP_AUDIO_IA.md`

## 4. Banco e migration

Nao houve migration nova.

A fase reaproveita:

- `agente_whatsapp_messages`
- `agente_whatsapp_processing_jobs`
- `agente_whatsapp_audio_artifacts`
- `agente_whatsapp_outbox`
- `agente_whatsapp_sessions`
- `orders`

## 5. Endpoint adicionado

- `GET /api/agente-whatsapp/audio/metrics?days=7`

O parametro `days` aceita de 1 a 90 dias.
O `response_model` valida a estrutura completa esperada pelo painel: periodo, audio, STT, TTS, jobs, custo e conversoes.

## 6. Estimativa de custo

Os custos sao estimativas operacionais internas:

- STT: calculado por minutos de audio com duracao disponivel.
- TTS: calculado por caracteres enviados para geracao de voz.
- A resposta inclui `pricing_note` avisando que nao substitui o billing oficial do provedor.

Constantes atuais:

- `STT_ESTIMATED_USD_PER_AUDIO_MINUTE = 0.006`
- `TTS_ESTIMATED_USD_PER_1K_CHARS = 0.015`

## 7. Conversoes

A atribuicao entregue e conservadora:

1. Considera mensagens do Agente com `campaign_id`.
2. Agrupa clientes e sessoes por campanha.
3. Busca pedidos do mesmo cliente em ate 7 dias apos a primeira mensagem da campanha.
4. Exclui pedidos cancelados/estornados.
5. Soma pedidos, receita e taxa de conversao por campanha.

## 8. O que ficou fora desta fase

- Billing real do provedor.
- Attribution multi-touch avancado.
- Vinculo hard `conversion_order_id` em banco.
- Dashboard BI externo ao modulo Agente WhatsApp.
- Metricas por tenant/company.

Esses itens permanecem para fases futuras ou BI avancado.

## 9. Validacao esperada

- `git diff --check`
- `npm.cmd run typecheck`
- `npm.cmd test`

Validacao comercial real depende de campanhas com `campaign_id`, clientes vinculados e pedidos no periodo.

## 10. Liberacao para Fase 9

A Fase 9 pode iniciar com foco em robustez e producao:

- Rollout com flags.
- Checklist VPS.
- Retencao/LGPD para audios.
- Observabilidade operacional.
- Validacao real WhatsApp em dispositivos.
