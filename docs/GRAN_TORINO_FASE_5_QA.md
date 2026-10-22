# Gran Torino — Fase 5: gates de arquitetura e QA

Este documento define os gates para a execução PCP e a transformação de estoque.
Ele complementa o contrato da Fase 0 e não libera planejamento, previsão ou
capacidade, que pertencem à Fase 8.

## Limites da fase

- A transformação usa a receita de preparo versionada e o rendimento aprovado.
- O alvo preparado é um `inventory_item` oficial; não existe cadastro paralelo.
- A execução debita lotes de origem e credita o lote produzido na mesma transação.
- O consumo posterior do preparado baixa apenas o lote preparado. Os
  ingredientes de origem não são baixados novamente.
- Produção parcial, perda e descarte são eventos explícitos. Quantidade
  planejada que não foi apontada não vira perda automaticamente.
- Cada conclusão tem identidade idempotente por tenant e execução. Repetição da
  mesma requisição retorna o resultado original; conteúdo divergente retorna
  conflito.
- A validade do lote produzido segue a política persistida e nunca pode
  ultrapassar a validade efetiva dos insumos sem uma regra aprovada e auditada.
- A fase não cria planejamento semanal, previsão de demanda, capacidade,
  compras ou distribuição multioperador.

## Gates bloqueadores

### PCP01 — Receita e grafo

Receitas de preparo exigem alvo preparado, unidade e rendimento positivo. O
grafo de receitas deve rejeitar ciclo direto e indireto antes de criar ou
publicar a versão. A composição usada pela execução fica congelada por versão;
alteração posterior não reescreve histórico.

### PCP02 — Transformação atômica

Uma execução deve manter, em um único commit, operação, débitos de origem,
crédito do lote produzido, genealogia e auditoria. Falha em qualquer etapa
deixa o saldo e os registros anteriores intactos. Locks seguem ordem estável
por item/lote e revalidam o saldo após o lock.

### PCP03 — Parcial e perda

Apontamentos aceitam somente quantidade positiva dentro do saldo planejado,
salvo uma correção autorizada com motivo. A soma das execuções não pode exceder
o planejado. Perda exige quantidade, motivo, ator e operação própria; retry não
duplica perda nem produção.

### PCP04 — Tenant e autorização

Toda leitura e mutação exige contexto tenant. FKs compostas e unicidades devem
impedir cruzamento entre empresas. Preparador acessa apenas a superfície
operacional e não altera receita, rendimento, custo ou parâmetros de
planejamento. Comandos administrativos usam RBAC explícito.

### PCP05 — Idempotência e concorrência

Repetição com a mesma chave e payload devolve o mesmo resultado. Chave usada
com payload diferente retorna 409. Duas conclusões concorrentes de uma mesma
execução produzem um vencedor e um conflito explícito, sem saldo negativo ou
dupla genealogia.

### PCP06 — Reconciliação

O detalhe da execução deve mostrar planejado, produzido, consumido, perdido e
restante. O restante só é baixado por novo apontamento explícito ou fechamento
autorizado; não pode ser inferido como perda.

## Validação mínima

1. Executar Alembic do banco descartável até o head único e inspecionar as
   constraints de receita, execução, lote e movimento.
2. Validar dois tenants, tentativa com IDs forjados, RBAC de preparador e
   isolamento de leitura/mutação.
3. Validar 20 kg em 40 porções de 300 g, apontamento parcial, perda motivada,
   consumo de uma porção e saldo restante sem baixa duplicada.
4. Executar retry da mesma chave, payload divergente e duas transações
   concorrentes no PostgreSQL.
5. Injetar falha depois do débito e depois do crédito e confirmar rollback
   integral.
6. Rodar regressão de inventário, receitas, CMV, pedidos, KDS e recebimento
   fiscal; depois executar build do cliente e servidor.

## Critério de conclusão

A Fase 5 só pode ser declarada concluída quando todos os gates PCP01–PCP06
estiverem evidenciados em PostgreSQL descartável, a migration estiver alinhada
ao head operacional único e não houver pendência de tenant, transação,
idempotência ou regressão ocultada por testes SQLite.
