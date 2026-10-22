# Gran Torino - Fase 6: gates de consulta tecnica KDS

Este documento define os gates da Fase 6. A fase expoe ao operador autorizado a
composicao tecnica congelada do pedido no KDS, sem criar uma segunda receita e
sem produzir efeito colateral no estoque, no pedido ou no financeiro.

## Limites da fase

- A origem da ficha e o snapshot persistido do item do pedido (`composition_json`)
  quando ele existir; a consulta nao recalcula o passado a partir da receita
  atualmente ativa.
- O retorno pode conter produto, quantidade, sabores, fracoes, ingredientes,
  metodos, remocoes e substituicoes necessarios ao preparo.
- O retorno nao pode conter custo, CMV, preco, pagamento, telefone, endereco ou
  qualquer outro dado de entrega.
- A leitura deve reutilizar a barreira existente de estacao KDS e a permissao
  `cozinha:view`; nenhuma conta de cozinha recebe CRUD de estoque ou receitas.
- Pedido e snapshot devem ser filtrados pelo tenant do contexto confiavel. IDs
  enviados pelo cliente nao escolhem tenant.
- A consulta e somente leitura: nao cria movimento, reserva, consumo, nova
  versao de receita, auditoria de mutacao ou transicao de pedido.

## Gates bloqueadores

### KCI01 - Snapshot imutavel

Depois que a receita ativa for alterada, a consulta do pedido antigo continua
retornando a composicao congelada no snapshot. Se o item nao possuir snapshot
tecnico, o contrato deve indicar pendencia explicita; nao deve inventar uma ficha
com a receita atual.

### KCI02 - DTO operacional sem dados sensiveis

O envelope deve permitir a ficha necessaria para montar o item, mantendo fora
do DTO custos, unit_cost, total_price, CMV, payment, delivery address, telefone e
identidade do cliente. O teste deve verificar tambem que os campos nao aparecem
em erros ou payloads de fallback.

### KCI03 - Tenant e estacao

Um operador nao consegue consultar pedido, item, receita, imagem ou snapshot de
outro tenant por ID forjado. Conta de estacao cozinha somente acessa o caminho
KDS autorizado; endpoints administrativos de inventario continuam bloqueados.

### KCI04 - Nenhum efeito colateral

Antes e depois da consulta, saldos, movimentos, reservas, status do pedido,
versoes de receita e registros de auditoria de mutacao permanecem iguais.

### KCI05 - Regressao do fluxo

As rotas existentes de iniciar preparo, marcar pronto, expedicao e retirada
continuam delegando ao `OrderService`. A consulta nao pode alterar a ordem das
transicoes nem expor detalhes de expedicao na superficie da cozinha.

## Validacao minima

1. Migrar um PostgreSQL descartavel ate o head unico e consultar um pedido com
   snapshot completo.
2. Alterar a receita depois da venda e confirmar que a consulta permanece igual.
3. Consultar item sem snapshot e confirmar estado de pendencia sem fallback
   inventado.
4. Repetir a leitura, comparar payload e verificar ausencia de writes.
5. Tentar IDs de outro tenant e usar conta de estacao fora do prefixo autorizado.
6. Executar regressao de receitas, CMV, pedidos, KDS e preparo, seguida do build
   do cliente e do servidor.

## Criterio de conclusao

A Fase 6 somente pode ser liberada quando KCI01-KCI05 tiverem evidencia em
PostgreSQL descartavel e os testes confirmarem que a consulta usa o snapshot
persistido, respeita tenant/RBAC e nao altera o ledger operacional.
