# AGENTE WHATSAPP - Fase 10

## Objetivo

Adicionar auditoria operacional da outbox no painel do AGENTE WHATSAPP para acompanhar mensagens pendentes, falhas e itens mortos sem depender de acesso direto ao banco.

## Entrega

- A central CRM do AGENTE WHATSAPP agora possui uma secao de auditoria da fila.
- Foram adicionados filtros por status:
  - todas
  - pendentes
  - falhas
  - mortas
  - enviadas
- A listagem mostra telefone, provider, tentativas, ultima atualizacao e previa da mensagem.
- Itens com erro exibem a mensagem de falha diretamente na tabela.
- O detalhe do item mostra:
  - id do item
  - id da mensagem
  - provider
  - proxima tentativa
  - erro completo
  - provider message id, quando existir
- Itens `failed`, `dead` e `pending` podem ser reprocessados seletivamente.
- Se houver itens `dead`, o painel mostra alerta visual.

## Backend

- `AgenteWhatsAppOutboxOut` agora inclui `message_type` e `message_body`.
- `AgenteWhatsAppOutboxService.serialize_outbox` retorna uma previa segura da mensagem relacionada.
- Nao houve mudanca de schema de banco nesta fase.

## Frontend

- A implementacao ficou em `client/pages/admin/crm/CrmAgenteWhatsApp.tsx`.
- A integracao continua passando apenas por `client/lib/api.ts`.
- O layout principal da conversa foi preservado.

## Proxima fase sugerida

Fase 11: alertas operacionais e politica de escalonamento para itens `dead`, incluindo notificacao no painel e regra para pausar provider com falhas repetidas.
