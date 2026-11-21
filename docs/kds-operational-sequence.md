# Sequencia operacional dos KDS

## Regra de roteamento

A ordem de apresentacao e Pizzaiolo, Esfiha, Forno, Expedicao. As bancadas de
pizza (`pizza`, `pizza-1`, `pizza-2`) e esfiha (`esfiha`) continuam recebendo os
produtos correspondentes. Uma pizza nao precisa de uma segunda montagem na
bancada de esfiha. Pedidos mistos mantem um unico pedido comercial e unidades
independentes, que se encontram na expedicao.

`ProductionUnit.station_id` preserva a bancada de origem, inclusive depois do
forno e no refazimento. O forno e representado pelos estados da tentativa
existente; nao ha nova tabela, estacao persistida ou pedido paralelo.

## Etapas e prioridade

- Fila -> conferencia de estoque -> montagem -> montada -> forno -> conferencia
  -> pronta -> fechamento na expedicao.
- Ao iniciar o forno, a tarefa sai da bancada de origem e aparece na expedicao,
  que conserva a acao existente de retirada e conferencia do forno.
- A expedicao so fecha unidades prontas. A liberacao do pedido inteiro aguarda
  todas as unidades; fechar uma unidade nao libera as que ainda estao no forno.
- Refazimentos usam a proxima `ProductionAttempt` da mesma unidade. A prioridade
  publicada e 1 para refazimento e 0 para a tentativa inicial.
- Trabalho ja aceito permanece a frente. Entre tarefas ainda na fila,
  refazimentos antecedem tarefas normais, com desempate por criacao e identidade.
- Conferencias de estoque ja solicitadas conservam FIFO; uma confirmacao tardia
  ou um refazimento nao pode ultrapassar a reserva de outro operador.

## Contratos e autorizacao

Os endpoints e permissoes atuais permanecem: `cozinha.view/edit/manage` para a
producao e redistribuicao, `expedicao.view/edit` para a expedicao. O tenant vem do
ator autorizado. As projecoes adicionam `operational_stage`; `station_id` continua
sendo a identidade da bancada de origem. O agrupamento legado de pizzas e
preservado; bancadas especificas nao veem unidades exclusivas de outra bancada.

## Aceite automatizado

As suites `test_kds_operational_sequence.py` e `test_kds_operational_dispatch.py`
cobrem transicoes, rejeicao de salto de etapa, estacoes existentes, tenant,
operador, prioridade, FIFO, refazimento e fechamento apos forno. As regressoes de
estoque, roteamento, RBAC e dispatch existentes tambem devem passar. SQLite
valida o comportamento; concorrencia de locks PostgreSQL exige ambiente proprio.

WhatsApp, checkout, bonificacoes e alteracao comercial de pedidos ficam fora
desta entrega. Esta mudanca nao e um deploy.

## Arquivos desta entrega

- `backend/core/kds_stations.py`: ordem e projecao da etapa operacional.
- `backend/services/kds_production_service.py`: transicoes, prioridade,
  compatibilidade de estacoes, propriedade do operador e auditoria.
- `backend/services/kds_service.py`: projecao por bancada e passagem pelo forno
  antes do fechamento na expedicao.
- `backend/schemas/kds_production.py` e `client/lib/api.ts`: campos aditivos de
  etapa e prioridade nos contratos existentes.
- `tests/test_kds_operational_sequence.py`: sequencia e prioridade.
- `tests/test_kds_operational_dispatch.py`: forno e fechamento na expedicao.
- `tests/test_kds_oven_routing.py`: regressao da fila com trabalho iniciado.

Comando de validacao do backend:

```powershell
python -m pytest tests/test_kds_operational_sequence.py tests/test_kds_operational_dispatch.py tests/test_kds_stock_gate.py tests/test_kds_oven_routing.py tests/test_fixed_pizza_stations.py tests/test_kds_esfiha_routing.py tests/test_kds_kitchen_dispatch.py -q --tb=short -p no:cacheprovider
```

Contrato TypeScript: `node node_modules/typescript/bin/tsc --noEmit --pretty false`.
