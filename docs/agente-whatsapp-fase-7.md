# AGENTE WHATSAPP - Fase 7

## Objetivo

Criar a central operacional visual do AGENTE WHATSAPP no grupo CRM do painel administrativo.

## Entregue

- Nova tela `client/pages/admin/crm/CrmAgenteWhatsApp.tsx`.
- Nova rota `/painel/crm/agente-whatsapp`.
- Novo item no menu CRM: `Agente WhatsApp`.
- Metadados da pagina no header global do painel.
- Integracao via `client/lib/api.ts`, sem chamadas `fetch` diretas no componente.

## Funcionalidades

- Dashboard rapido com conversas abertas, conversas em atendimento humano, IA pausada e mensagens do dia.
- Lista de conversas com filtros por status.
- Busca por telefone, cliente, provedor ou intencao atual.
- Criacao manual de sessao por telefone.
- Visualizacao do historico de mensagens.
- Controle operacional:
  - assumir conversa;
  - pausar IA;
  - devolver para IA;
  - encerrar conversa.
- Registro de resposta humana no historico como mensagem outbound em fila.

## Regras de seguranca

- A tela nao envia mensagem externa ao WhatsApp.
- A tela nao ativa IA autonoma.
- A tela nao cria pedidos nem pagamentos.
- Toda acao usa as rotas administrativas existentes do AGENTE WHATSAPP.
- O layout usa o shell global do painel; a pagina renderiza apenas conteudo.

## Proxima fase

A Fase 8 deve implementar outbox/fila/worker para envio real e assíncrono das mensagens `queued`, com retry, idempotencia, controle de erro e integracao ao provider.
