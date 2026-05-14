# AGENTE WHATSAPP - Fase 4

## Objetivo

Criar a camada operacional de tool calling do AGENTE WHATSAPP, reaproveitando os services reais do ERP sem permitir que a IA acesse banco diretamente ou invente dados.

## Entregue

- Registry backend de ferramentas em `backend/services/agente_whatsapp_tools.py`.
- Endpoints administrativos:
  - `GET /api/agente-whatsapp/tools`
  - `POST /api/agente-whatsapp/tools/execute`
- Auditoria persistida em `agente_whatsapp_tool_calls`.
- Migration Alembic e bootstrap runtime em `backend/main.py`.
- Tipos e metodos no frontend em `client/lib/api.ts`.

## Ferramentas disponiveis

- `buscar_cliente_por_telefone`
- `buscar_produtos`
- `buscar_produto_por_nome`
- `buscar_promocoes`
- `calcular_frete`
- `validar_cupom`
- `consultar_status_pedido`
- `consultar_pagamento`
- `buscar_enderecos`
- `buscar_ultimo_pedido`
- `buscar_fidelidade`

## Regras de seguranca

- A Fase 4 nao cria pedidos.
- A Fase 4 nao gera pagamentos.
- A Fase 4 nao envia mensagens externas.
- Todas as tools expostas sao de consulta ou validacao.
- Toda execucao fica registrada com argumentos, resultado, erro, latencia, sessao e cliente quando houver.

## Proxima fase

A Fase 5 deve usar esta base para orquestrar venda assistida: montagem de carrinho, validacao de item, criacao de pedido e geracao de pagamento, sempre por tools reais e com confirmacao explicita do cliente.
