# AGENTE WHATSAPP - Fase 18

## Objetivo

Adicionar guardrails operacionais para a IA do AGENTE WHATSAPP, reduzindo risco de loop, excesso de mensagens automaticas e envio quando a conversa esta em atendimento humano ou com automacoes bloqueadas.

## Entrega

- Guardrails no `AgenteWhatsAppAIService`.
- Endpoint administrativo:
  - `GET /api/agente-whatsapp/sessions/{session_id}/ai/guardrails`
- Resposta da IA passa a retornar o bloco `guardrails`.
- Painel CRM > Agente WhatsApp exibe aviso quando o envio automatico esta bloqueado ou em alerta.

## Regras Implementadas

- Bloquear `auto_queue=true` quando:
  - IA esta desativada na sessao.
  - automacoes estao bloqueadas.
  - conversa esta em status `human`, `ai_paused` ou `closed`.
  - sessao nao tem telefone.
  - a ultima mensagem ja foi da IA e ainda nao houve nova mensagem do cliente.
  - houve 2 ou mais respostas consecutivas da IA.
  - houve 5 ou mais respostas da IA em 10 minutos.
- Marcar alerta quando a conversa ja teve 3 ou mais respostas da IA em 10 minutos.
- Sugerir resposta no painel continua permitido, porque a decisao final permanece com o atendente.
- Guardrail bloqueado registra evento `agente_whatsapp_ai_response_blocked`.

## Estrutura Reaproveitada

- `agente_whatsapp_sessions`
- `agente_whatsapp_messages`
- `agente_whatsapp_events`

Nenhuma migration nova foi criada nesta fase.

## Criterio de Aceite

- O backend consegue auditar se a IA pode responder automaticamente.
- A IA nao enfileira resposta automatica em conversa pausada, humana, fechada ou sem nova mensagem do cliente.
- O painel mostra o motivo de bloqueio/alerta para o operador.
