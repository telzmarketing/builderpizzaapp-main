# AGENTE WHATSAPP - Fase 17

## Objetivo

Implementar a primeira camada operacional da IA vendedora do AGENTE WHATSAPP com tool calling real, sem depender de dados inventados e sem criar fluxo paralelo ao ERP.

## Entrega

- Novo runtime backend `AgenteWhatsAppAIService`.
- Endpoint administrativo:
  - `POST /api/agente-whatsapp/sessions/{session_id}/ai/respond`
- Integração no painel CRM > Agente WhatsApp com botão `Sugerir IA`.
- Registro de evento `agente_whatsapp_ai_response_generated`.
- Atualização de contexto curto e intenção atual da sessão.

## Regras Implementadas

- A IA chama apenas ferramentas registradas em `AgenteWhatsAppToolService`.
- Produtos, preços, promoções, cupons, frete, status, último pedido e fidelidade vêm dos serviços reais.
- Respostas automáticas enfileiradas respeitam `ai_enabled`, `automation_blocked`, atendimento humano e IA pausada.
- Por padrão no painel, a IA apenas sugere a resposta; o atendente ainda decide enviar.
- Quando `auto_queue=true`, a resposta é salva como mensagem outbound `sender_type=ai` e enviada para a outbox.

## Intenções Mapeadas

- `venda_cardapio`
- `promocoes`
- `calcular_frete`
- `validar_cupom`
- `consultar_status`
- `fidelidade`
- `recompra`
- `atendimento`

## Ferramentas Reutilizadas

- `buscar_cliente_por_telefone`
- `buscar_produtos`
- `buscar_promocoes`
- `calcular_frete`
- `validar_cupom`
- `consultar_status_pedido`
- `buscar_ultimo_pedido`
- `buscar_fidelidade`

## Limites Atuais

- Esta fase nao integra provedor LLM externo.
- A interpretacao e deterministica para manter seguranca comercial.
- Criacao automatica de pedido real continua protegida por confirmacao explicita via ferramenta existente.
- O envio em producao ainda depende da configuracao real do provider WhatsApp.

## Criterio de Aceite

- O painel consegue gerar uma sugestao de resposta baseada na ultima mensagem do cliente.
- O backend registra a trilha das ferramentas usadas.
- A resposta nunca cria preco, promocao, status ou beneficio fora das ferramentas reais.
