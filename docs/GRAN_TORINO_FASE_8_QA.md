# Gran Torino — Fase 8: QA da integração de consumo

## Escopo validado

A Fase 8 deve unificar o evento físico de consumo entre pedido, unidade/tentativa KDS, estoque bruto, estoque preparado e CMV. O pedido comercial permanece a autoridade do status de venda; a tentativa física deve apontar para uma composição/snapshot imutável e para a operação de estoque que efetivamente baixou os insumos.

Critérios mínimos derivados de `GRAN_TORINO_FASE_0_OPERACAO.md` e `GRAN_TORINO_FASE_0_CONTRATOS.md`:

1. O primeiro comando autoritativo de produção cria ou reutiliza uma única operação de consumo por tentativa, com idempotência persistente.
2. Repetição do mesmo comando retorna a mesma operação e não cria uma segunda baixa.
3. Uma tentativa de outro tenant não pode ser lida, alterada ou consumida.
4. O consumo usa o snapshot operacional da tentativa, sem resolver receita mutável no momento do retry.
5. Insumos brutos, preparados e reservas são consumidos pelo serviço de estoque existente, na mesma transação da transição KDS.
6. Falha de qualquer etapa faz rollback integral: estado, operação, movimentos, reservas e linhas de consumo.
7. Refazimento cria nova tentativa e novo consumo; não reutiliza nem duplica o consumo anterior.
8. O consumo legado por pedido não pode ocorrer novamente para uma tentativa já coberta pelo novo fluxo.
9. A resposta da API distingue `attempts`, `legacy_covered` e `not_required`, expondo `consumption_operation_id` quando aplicável.
10. Concorrência PostgreSQL com duas sessões produz no máximo uma operação e uma baixa para a mesma tentativa.

## Evidência executada nesta revisão

- `python -m py_compile backend/models/kds_production.py backend/services/kds_production_service.py backend/routes/kds.py backend/schemas/kds_production.py`: aprovado.
- Importação do router KDS: aprovada, 23 rotas carregadas.
- A migration `20261022_kds_attempt_consumption.py` foi localizada com `down_revision=20261022_kds_production` e cria `production_attempt_consumptions` com FK tenant-safe, quantidade positiva e unicidade por tentativa/insumo.

## Pendências que impedem declarar a fase concluída

Na revisão atual, a tabela de auditoria da tentativa já existe, mas não foi encontrada uma implementação comprovada que execute a baixa de estoque e associe `movement_ids`/`operation_id` à transição KDS. Também não há evidência de teste PostgreSQL concorrente, rollback por falha intermediária, isolamento entre tenants, refazimento com novo consumo ou reconciliação CMV.

Enquanto esses testes e o serviço transacional não estiverem presentes, a migration é somente estrutura persistida; ela não prova integração de consumo. A validação local de compilação também não prova compatibilidade do schema com PostgreSQL nem segurança de concorrência.

## Gate de aceite QA

A Fase 8 pode ser marcada como concluída após:

- testes unitários do serviço para idempotência, retry, refazimento, preparado, bruto e legado;
- testes PostgreSQL com duas sessões independentes e rollback induzido;
- teste de autorização e tenant cruzado por HTTP;
- validação da migration a partir do head operacional e consulta ORM das novas tabelas;
- teste frontend verificando o modo de consumo e o identificador da operação retornados pelo backend;
- build frontend e execução do conjunto regressivo KDS/estoque.

