# Gran Torino - Fase 7: gates de QA e aceite operacional

Este documento transforma os contratos da Fase 0 em gates verificaveis para a Fase 7 (KDS multioperador, distribuicao, presenca, relogios e redistribuicao). A fase so pode ser declarada concluida quando os gates abaixo tiverem evidencia separada para testes estaticos, PostgreSQL transacional e HTTP autenticado.

## Escopo de aceite

1. A unidade fisica de producao permanece vinculada ao `tenant_id`, `order_item_id` e `unit_index`; uma ordem comercial nao e duplicada para criar uma tarefa.
2. Tentativas, snapshots operacionais, atribuicoes, estados do operador e comandos possuem referencias tenant-safe, unicidades e versao persistida no banco.
3. A fila do operador deriva do ator autenticado. Nenhum `operator_id`, `tenant_id` ou quantidade derivada da receita pode ser escolhido por query/body.
4. Os comandos mutantes exigem `expected_version` e `Idempotency-Key`. Replay com o mesmo hash retorna o efeito original; a mesma chave com payload diferente retorna `409 IdempotencyConflict`.
5. Inicio, consumo e evento persistente devem confirmar na mesma transacao. Uma corrida de duas sessoes produz no maximo uma tentativa ativa e uma baixa.
6. `finish-assembly`, forno e conferencia avancam somente estados permitidos. A conclusao da montagem nao marca o pedido como pronto.
7. Refazimento permanece limitado a pedido em `preparing` ate decisao explicita sobre retrabalho tardio. `ready_for_pickup`, `on_the_way` e `delivered` retornam `409 LateReworkNotSupported` sem tentativa, consumo ou regressao.
8. Presenca e heartbeat nao reativam operador pausado implicitamente. Offline, pausado e sem capacidade nao recebem atribuicoes.
9. Distribuicao concorrente usa lock de decisao por tenant/estacao, ordem estavel e unicidade de atribuicao; tarefas iniciadas nao migram automaticamente.
10. Payload operacional nao expoe custos, pagamento, endereco, telefone, compras ou credenciais.

## Matriz de autorizacao

| Superficie | Papel/permissao | Regra de isolamento |
| --- | --- | --- |
| `/api/kds/kitchen/...` | estacao/cozinha com `cozinha:view/edit` | prefixo de estacao permanece restrito |
| `/api/preparation/...` | preparador com permissao operacional propria | sem acesso a planejamento gerencial |
| `/api/kds/management/redistributions` | gerente com permissao explicita | motivo obrigatorio e tarefas do mesmo tenant |
| composicao | leitura operacional | sem CMV, custo ou dados de entrega |

Testes HTTP devem cobrir: operador autorizado, operador sem a permissao, outro tenant com ID conhecido e conta de estacao tentando acessar prefixo alheio. IDs fora do tenant devem responder como recurso inexistente ou erro de escopo sem revelar existencia.

## Gates de concorrencia e idempotencia

- duas sessoes iniciam a mesma tarefa com a mesma versao: uma vence e a outra recebe conflito, sem duplicar consumo;
- duas sessoes distribuem a mesma fila: nao ha atribuicao duplicada nem carga perdida;
- replay depois de timeout retorna a resposta persistida sem novo movimento;
- chave idempotente com hash diferente nao altera estado;
- rollback em falha de consumo ou evento nao deixa tentativa, baixa ou evento parcial;
- refazimento cria tentativa nova somente quando o estado comercial permite e nao copia a baixa anterior.

## Evidencia minima para liberar

- `alembic heads` retorna exatamente um head e todos os targets operacionais apontam para ele;
- migration sobe de uma copia descartavel da base atual e uma copia nova vazia, sem DDL manual;
- testes PostgreSQL com duas conexoes comprovam locks, constraints, tenant isolation e rollback;
- testes de contrato verificam rotas, schemas, RBAC e envelope de erro;
- build do frontend e compilacao do backend passam;
- a tela conserva timestamps do servidor apos reload/reconexao e nao repete mutacao automaticamente;
- nenhum deploy ou validacao VPS e inferido a partir desses testes locais.

## Pendencias que bloqueiam conclusao

- definir formalmente retrabalho tardio e sua destinacao financeira;
- confirmar a matriz de etapas por produto e quais itens exigem forno/conferencia;
- confirmar a politica de capacidade, prioridade, tolerancia de desconexao e atraso;
- demonstrar que o mecanismo de eventos nao usa o status global como ACK de consumidor concorrente;
- se etiquetas forem incluidas, validar origem lote/execucao sem afrouxar os contratos legados de pedido.

