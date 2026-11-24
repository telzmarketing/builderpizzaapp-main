# Compras e Suprimentos — Lote 2: Planejamento de necessidades

## Entrega

O planejamento é uma consulta somente de leitura em:

`GET /api/gestao/purchases/requisitions/planning/needs`

O tenant é obtido do contexto autenticado e a consulta exige a permissão `inventory.view`.
O endpoint não cria requisição, compra, movimento de estoque ou reserva.

## Cálculo

Para itens diretos, o serviço consolida:

- soma dos movimentos de estoque do tenant;
- reservas ativas e não expiradas;
- compras confirmadas como quantidade em trânsito;
- estoque mínimo do item;
- unidade-base cadastrada.

`disponível = max(estoque atual - reservas ativas, 0)`

`sugerido = max(estoque mínimo - disponível - em trânsito, 0)`

Itens de saída de uma configuração ativa de porcionamento são calculados pelo contrato existente de alertas de reposição de porções. Conversões ausentes ou inválidas não viram zero: ficam bloqueadas para revisão.

## Estados e ações

| Estado | Ação | Significado |
| --- | --- | --- |
| `confirmed` | `covered` ou `purchase_required` | cálculo direto baseado em dados confirmados |
| `pending` | `covered` ou `review_required` | existe cobertura em trânsito ou a configuração é opcional |
| `estimated` | `purchase_required` | necessidade depende de estimativa do porcionamento |
| `blocked` | `review_required` | unidade/conversão ou referência obrigatória está inválida |
| `unavailable` | `review_required` | estado reservado para indisponibilidade operacional explícita |

## Interface

A aba `Reposição de Estoque` apresenta os itens, disponibilidade, mínimo, trânsito, quantidade sugerida, estado, ação e motivo. A atualização é manual e preserva o fluxo existente de criação explícita de compras fora desta tela.

## Critérios validados

- tenant e RBAC aplicados na rota;
- cálculo sem valores negativos;
- nenhuma escrita no planejamento;
- tipagem frontend/backend alinhada;
- testes focados de compras, estoque, porcionamento e contexto passaram;
- build deve ser executado antes de qualquer publicação.
