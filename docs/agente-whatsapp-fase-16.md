# AGENTE WHATSAPP - Fase 16

## Objetivo

Adicionar automacoes comerciais do AGENTE WHATSAPP para recompra, carrinho abandonado, aniversario, fidelidade e reativacao.

## Entrega

- Criado motor de automacoes comerciais dentro do `AgenteWhatsAppService`.
- Criadas automacoes operacionais:
  - recompra
  - reativacao
  - carrinho abandonado
  - aniversario
  - fidelidade
- Criada previa de clientes elegiveis antes do envio.
- Envio usa sessoes, mensagens e outbox oficiais do AGENTE WHATSAPP.
- Deduplicacao por cliente usando `agente_whatsapp_events`.
- Worker passa a processar automacoes comerciais de forma incremental.
- Painel permite:
  - escolher automacao
  - ajustar limite
  - editar mensagem
  - ver previa
  - enfileirar envios
  - rodar todas as automacoes comerciais

## Endpoints

- `GET /api/agente-whatsapp/automations/templates`
- `POST /api/agente-whatsapp/automations/run`
- `POST /api/agente-whatsapp/automations/run-due`

## Regras

- Toda mensagem respeita telefone valido e permissao/canal WhatsApp.
- O mesmo cliente nao recebe a mesma automacao novamente dentro do cooldown definido.
- A automacao apenas cria mensagens `queued`; o envio real continua passando pela outbox.
- Carrinho abandonado usa eventos `cart_item_added` ou `add_to_cart` com mais de 60 minutos e sem pedido posterior.
- Fidelidade usa clientes com pontos disponiveis.
- Aniversario usa `birth_date` do cliente.

## Proxima fase sugerida

Fase 17: IA vendedora com tool calling completo, usando ferramentas reais para cardapio, promocoes, frete, cupons, pedidos, pagamentos e fidelidade.
