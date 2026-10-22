# Gran Torino - Fase 4: revisão arquitetural e gates de QA

## Escopo

A Fase 4 trata rastreabilidade física do estoque: abertura de recipientes,
validade efetiva, seleção FEFO, genealogia e etiquetas. O ledger de
movimentos continua sendo a autoridade do saldo. A fase não cria um segundo
estoque, não altera o catálogo comercial e não converte uma solicitação de
impressão em prova de impressão física.

## Decisões que a implementação precisa preservar

- Todo lote, abertura, alocação e vínculo de etiqueta pertence a um tenant e
  usa referências tenant-safe.
- Lote sem validade não é elegível até existir uma política aprovada para o
  item. Vencido, bloqueado, em quarentena ou descartado não pode ser
  reservado nem consumido.
- FEFO ordena por validade efetiva, recebimento e identificador. A validade
  efetiva considera a regra mais restritiva entre origem, abertura e
  armazenamento; nenhuma transformação pode ampliar o prazo.
- Abertura parcial gera evento imutável e recipiente derivado quando a regra
  exigir subdivisão. Recipientes fechados conservam sua validade original.
- Alocação física referencia a mesma revisão de composição e o mesmo lote que
  será consumido. Consulta, retry e reimpressão não movimentam saldo.
- Etiqueta de lote/preparo deriva de dados persistidos do lote: item,
  quantidade, validade, armazenamento, responsável e tenant. Reimpressão
  exige motivo quando configurado e deixa um evento auditável.
- O contrato antigo de etiquetas de pedido continua válido. A extensão para
  origem de lote ou preparo deve ser explícita; não usar pedido fictício para
  satisfazer uma FK.

## Contratos de aceite

1. Criar ou receber um lote exige item, local, código, ator e identidade do
   tenant. Datas inconsistentes são rejeitadas.
2. A abertura exige versão esperada, quantidade positiva e regra de validade.
   Repetição da mesma chave de idempotência retorna o mesmo resultado sem
   novo lote, movimento ou evento.
3. O bloqueio de um lote conserva seu saldo e sinaliza reservas ou execuções
   afetadas. Não libera compromissos silenciosamente.
4. A seleção FEFO exclui estados inelegíveis e revalida a validade dentro da
   transação. Duas sessões concorrentes nunca alocam mais que o saldo
   disponível.
5. A genealogia permite seguir lote de origem para saída/preparo e dessa
   saída para consumo. Falha parcial faz rollback da operação completa.
6. Gerar uma etiqueta cria apenas uma versão e um job idempotente. Imprimir
   novamente exige motivo e não repete produção, consumo ou baixa.
7. Um identificador de outro tenant retorna 404/escopo equivalente e não
   revela sua existência. Payload, query, header e nome de arquivo não podem
   escolher o tenant.

## Revisão de integração existente

As rotas atuais de inventário e o serviço de estoque devem continuar sendo os
únicos escritores do ledger. As rotas de KDS continuam responsáveis pelo
estado operacional do pedido; a Fase 4 não redefine `preparing` ou
`ready_for_pickup`. A infraestrutura existente de `LabelPrinter`,
`LabelTemplate`, `LabelVolume` e `LabelPrintJob` deve ser reutilizada, com
extensão de origem apenas onde a migration tornar a origem explícita.

O operador de cozinha consulta composição e tarefa pelo limite KDS existente.
Dados de custo, fornecedor e saldo global não entram no DTO operacional da
estação sem permissão específica.

## Gate de migration e release

As migrations novas devem formar uma única cadeia a partir do head da Fase 3.
Antes de qualquer publicação, executar em banco descartável:

```text
alembic -c backend/alembic.ini heads
alembic -c backend/alembic.ini history --verbose
alembic -c backend/alembic.ini upgrade 20261022_inventory_traceability
```

Confirmar que a versão do banco coincide com o head, que todas as tabelas e
constraints da Fase 4 existem e que o downgrade destrutivo não é usado como
rollback de produção. O cutover permanece forward-only e precisa preservar
backup e evidência de recuperação.

## Plano de validação

- Testes estáticos: imports do modelo, cadeia Alembic, constraints, rotas,
  RBAC e `git diff --check`.
- Testes de serviço: validade efetiva, abertura parcial, FEFO, bloqueio,
  genealogia, idempotência e reimpressão.
- PostgreSQL: dois tenants, três lotes por item, empate de validade, duas
  sessões concorrentes e rollback após falha de uma etapa.
- Regressão: inventário legado, recebimento da Fase 3, checkout, KDS,
  expedição e testes existentes de labels.
- Frontend: loading, erro, vazio, conflito de versão, replay da ação e
  feedback de impressão solicitado.
- Build: compilação Python, build cliente/servidor e somente depois o ciclo
  de restart/health em ambiente de validação.

## Evidência e limites

Passar em testes unitários ou em `/health` não comprova impressão física,
integração com uma impressora piloto, política sanitária ou operação em VPS.
Esses itens exigem evidência operacional separada e não devem ser marcados
como concluídos pela validação estática.
