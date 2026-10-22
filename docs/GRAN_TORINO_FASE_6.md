# Gran Torino — Fase 6: KDS interativo

## Entrega

- O KDS consulta a composição técnica congelada no snapshot do pedido.
- A tela de cozinha exibe gramagens, componentes comuns, sabores, frações, ingredientes, substituições e métodos de montagem.
- Pedidos sem snapshot permanecem explicitamente pendentes; nenhuma receita atual é aplicada retroativamente.
- A resposta operacional não expõe preço, CMV, pagamento, endereço ou telefone.
- A leitura é tenant-safe, protegida pela permissão `cozinha:view` e sem efeitos colaterais.

## Limites

Estados, filas, distribuição, temporizadores e redistribuição multioperador pertencem à Fase 7. A Fase 6 não cria consumo, reserva ou movimentação de estoque.
