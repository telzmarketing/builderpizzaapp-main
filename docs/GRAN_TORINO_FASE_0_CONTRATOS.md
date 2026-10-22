# Gran Torino — Fase 0: contratos de estoque e composição

**Status:** especificação técnica proposta, não publicada e não implementada. Documentação da Fase 0; não autoriza implementação, alteração do banco, migration ou deploy.

**Base revalidada:** commit `4d553bf1e7678d65f22616b93c733fbb470afc2f`, em 21/10/2026. A confirmação decorre de leitura de código local; não comprova estado de banco, VPS ou CI. Os nomes novos abaixo são propostas; os nomes existentes são identificados explicitamente.

## 1. Limites e decisões técnicas

- Catálogo comercial continua em `products`, `product_sizes`, `product_crust_types` e variantes existentes. Insumos e preparações utilizam `inventory_items`; fornecedores utilizam `inventory_suppliers`.
- Estoque físico continua derivado de `inventory_stock_movements`. Uma projeção de saldo poderá otimizar consultas, mas deve ser reconstruível e nunca editável como fonte independente.
- `InventoryService`, o motor `recipe_resolution.py`, os snapshots CMV e `FinanceService` são pontos de evolução. Rotas delegam a services; frontend chama exclusivamente `client/lib/api.ts`.
- Compra, documento fiscal recebido, recebimento físico, obrigação financeira e pagamento são fatos diferentes. Nenhum deles prova automaticamente os demais.
- Quantidades e valores novos usam Decimal/NUMERIC; novos contratos não alteram silenciosamente os JSON numéricos dos contratos publicados.
- Toda operação física confirmada possui identidade persistente, autor, motivo, data, origem, linhas e eventual compensação. Publicar evento em memória não é prova de entrega durável.
- Prazos sanitários, política contábil, alçadas e tolerâncias dependem das decisões do gestor listadas na seção 12. Até sua definição, a funcionalidade correspondente não pode ser ativada em produção.

## 2. Evidências do código existente

| Evidência | Consequência para a implementação futura |
| --- | --- |
| `backend/models/inventory.py:13-164`: unidades, categorias, locais, fornecedores, insumos, compras, entradas e movimentos; quantidades/custos em Float | Estender o domínio existente e planejar conversão decimal, sem segundo estoque |
| `backend/models/inventory.py:167-210`: versões e ingredientes; `component_role`, `reference_fraction`, escopos por opções do catálogo | Não recriar fichas ou cadastro comercial |
| `backend/services/inventory_service.py:203-257`: compra confirmada publica evento depois do commit | Confirmar compra não representa entrada física; entrega financeira requer reconciliação |
| `backend/services/inventory_service.py:329-404`: flags, baixa em `preparing`, locks de pedido/insumos, saldo agregado | Preservar comportamento e evoluir unidade de consumo sem dupla baixa |
| `backend/services/inventory_service.py:406-472`: perda pós-início sem devolução automática | Separar cancelamento comercial, perda e retorno físico comprovado |
| `backend/services/inventory_service.py:494-534`: edição cria versão, exclusão desativa | Preservar histórico, inclusive depois de criar execução por item |
| `backend/services/inventory_service.py:592-638`: soma de movimentos e média de entradas positivas | Não chamar a média atual de custo médio móvel validado |
| `backend/services/recipe_resolution.py:25-92`: fração ocupada/referência e desperdício | Reutilizar motor, migrar sua aritmética para Decimal e formalizar unidades |
| `backend/services/cmv_snapshot_service.py:53-71`: snapshot também habilitado por estoque ativo com `sales_control_enabled`, mesmo sem dashboard CMV | Snapshot não depende exclusivamente da flag CMV |
| `backend/models/finance.py:68-117`: títulos, parcelas, centro de custo e vínculo de compra | Reutilizar contas a pagar; não criar módulo financeiro paralelo |
| `backend/services/finance_service.py:482-547`: confirmação cria um título pela compra, vencimento por `expected_date` | Evoluir origem documental e parcelas sem duplicar obrigação preexistente |
| `backend/routes/inventory.py:34-67`: sucesso direto via DTO/lista; erros usam `err` | Não presumir envelope de sucesso universal |
| `backend/core/response.py`; `backend/core/exceptions.py`; `backend/core/rbac_authorization.py` | Reutilizar formatos e mecanismo de autorização reais |
| `backend/core/seed.py:341-342,392-393`: módulos `inventory` e `cmv`; módulo `financeiro` já existente | Reutilizar chaves RBAC e permissões existentes |

Não foram identificados no domínio de inventário atual modelos de lotes, conversões por embalagem, recebimentos conferidos, reservas persistentes ou ordens de preparo. Essa constatação não significa ausência de campos homônimos em outros domínios.

### Inventário de escritores e gate obrigatório da fundação

| Caminho atual | Comportamento observado e revisão necessária |
| --- | --- |
| `InventoryService.create_manual_entry`, `inventory_service.py:269-284,812-827` | Cria origem e movimento, com commit próprio; incorporar conversão, operação, lote e protocolo de locks antes de ativar fundação nova |
| `InventoryService.delete_manual_entry`, `inventory_service.py:286-293` | Apaga movimentos da origem e depois entrada; o ledger atual não é integralmente imutável. Substituir efeito destrutivo por compensação autorizada quando houver novos lotes/operações |
| Atualização de entrada manual | Não foi localizado método `update_manual_entry` no service/rota revalidado; qualquer fluxo futuro de edição, recriação ou importação deve participar do mesmo gate, sem presumir que seja seguro |
| Compra criada/editada/confirmada, `inventory_service.py:203-257` | Reescreve linhas em rascunho; confirmada fica protegida e dispara financeiro. Não produz recebimento físico; conferir consumidores antes de integrar novas entradas |
| Pedido público e salão, `order_service.py:796,925,1011-1013,1138-1157,1274-1278` | Há snapshot na criação; salão nasce `preparing` e consome na criação, além da transição posterior usada por outros canais. Auditar loja, salão, admin e todas integrações que delegam criação/status, não apenas botão KDS |
| Snapshots e consultas de custo, `cmv_snapshot_service.py:73-132,176-196`; `cmv_service.py:116-125` | Escrevem histórico ou leem a média Float atual; migrar precisão e semântica sem recalcular snapshots publicados |
| Exclusão de pedido, `order_service.py:1341-1364` | Bloqueia exclusão quando encontra movimentos `order_sale/order_sale_reversal`; ampliar proteção para operações/execuções/lotes novos e revisar escopo tenant |
| Baixa, reversão/perda e publicação de ficha | Revisar junto dos caminhos acima: precisam compartilhar invariantes de identidade, precisão, versão e bloqueio |

**Gate da Fase 1:** nenhum escritor legado pode recalcular, recriar, apagar ou compensar movimentos vinculados a lotes/Decimal novos fora do service canônico. Ativação fica bloqueada até inventário de todos os chamadores, tratamento de exclusões e regressões dos canais existentes. A imutabilidade documentada para operações novas é requisito futuro, não descrição garantida do ledger atual.

## 3. Modelo incremental proposto

Todas as tabelas novas: `id` String compatível com o projeto, `tenant_id NOT NULL`, timestamps com fuso, ator de criação e versão de concorrência quando mutáveis. Entidades referenciadas exigem unique `(tenant_id,id)` e FKs compostas, evitando filhos de outro tenant. Documento e operação confirmados são imutáveis; correção usa revisão ou compensação vinculada. Exclusão de origem auditável usa RESTRICT, não cascata destrutiva.

| Entidade proposta ou extensão | Campos/relacionamentos essenciais | Constraints/índices essenciais |
| --- | --- | --- |
| `inventory_item_packagings` | item existente, fornecedor opcional, unidade comercial, unidade base, fator, peso variável, vigência, revisão | fator positivo; índice tenant/item/fornecedor; revisão imutável após uso |
| `inventory_receipt_documents` | fornecedor, chave NF-e, número/série, CNPJ emissor, emissão/entrada, totais, status, versão, compra opcional | unique parcial tenant/chave preenchida; identidade alternativa fiscal normalizada; índices tenant/status/emissão |
| `inventory_receipt_document_lines` | documento, linha origem, código fornecedor/GTIN, descrição original, quantidades/unidades comerciais e tributáveis, valor, associação confirmada, pendências | unique tenant/documento/linha; dados extraídos separados dos conferidos |
| `inventory_document_extractions` | documento, arquivo privado, hash, método XML/texto/OCR, versão extrator, campos/evidências/confiança, erros | índice tenant/documento; extrações imutáveis; hash não substitui identidade fiscal |
| `inventory_supplier_item_mappings` | fornecedor, código, GTIN/embalagem contextual, insumo, conversão revisada, confirmado por/em | unique na identidade contextual normalizada; nenhuma associação automática de baixa confiança |
| `inventory_receipts` e linhas | documento/compra opcionais, sequência de recebimento, conferente, quantidades aceitas/rejeitadas, original e normalizada, conversão/custo congelados, operação | unique tenant/documento/sequência; impedir recebimento acumulado acima do documento sem ajuste aprovado |
| `inventory_lots` | item, fornecedor/origem, código externo, lote interno, fabricação, validade original/efetiva, estado, local, recipiente/lote pai opcional | código externo não é unique global; índice FEFO tenant/item/estado/validade/id |
| `inventory_lot_openings` | lote ou recipiente, data de abertura, regra aplicada, responsável, validade resultante | evento imutável; abertura parcial subdivide recipiente/lote antes de alterar validade |
| `inventory_operations` e linhas | tipo, entidade origem, execução, idempotency key/hash, estado, ator, revisão de entrada e referências de compensação | unique tenant/tipo/identidade negócio; unique tenant/escopo/key; resultado persistido no commit |
| extensão de `inventory_stock_movements` | operação, linha lógica, sequência física, lote, local, quantidade decimal, custo decimal, movimento compensado | unique tenant/operação/sequência; linha lógica pode originar vários movimentos/lotes; manter uniques legados até migração verificada |
| alocações de consumo | execução/item pedido/unidade, movimento referenciado | derivadas dos movimentos ou vínculo 1:1 unique tenant/movimento; lote/quantidade/custo do movimento são autoridade, sem segunda cópia editável |
| extensão das receitas existentes | unidade da linha, sequência, instrução/imagem privada, regras de montagem; referência explícita | unidade compatível com insumo; nenhuma reinterpretação global de fichas antigas |
| receitas de preparo e ordens | alvo `inventory_item`, rendimento/unidade, versão, ordem, quantidade prevista/real, perdas, lotes de origem/saída | mesma composição de insumos e mesma movimentação; rejeitar ciclos e saída sem insumos alocados |
| vínculo financeiro documental | documento, título/parcela existente, natureza e valor vinculado | unique tenant/documento/parcela para geração; conciliar título antigo antes de criar |

Decisão arquitetural proposta para receitas de preparo: estender `inventory_recipe_versions`/`inventory_recipe_items` com `recipe_kind` (`commercial` padrão legado, `preparation` para transformação) e alvo exclusivo (`product_id` comercial OU `output_inventory_item_id` preparado). Adicionar `yield_quantity NUMERIC(20,6)` e `yield_unit_id` obrigatório no tipo preparo, com rendimento positivo. CHECK: comercial exige product e não aceita output; preparo exige output e não aceita product. FKs do alvo/unidade incluem tenant. `component_role/reference_fraction` continuam sendo o contrato comercial; preparo usa rendimento, sem aplicar fração de pizza. O `product_id` atual é obrigatório: relaxá-lo somente na mesma migration que impõe CHECK, backfill de `recipe_kind`, filtros comerciais em todos os consumidores, schemas discriminados e regressão. Não criar receita independente para o KDS. A implementação desse desenho continua sujeita à aprovação da próxima fase.

Decisão F0 para identidade operacional, com nomes de tabela propostos: `production_units(id,tenant_id,order_item_id,unit_index)` unique tenant/item/índice inteiro positivo representa cada unidade física vendida sem duplicar item comercial. `production_attempts(id,tenant_id,production_unit_id,attempt_number,composition_revision_id,previous_attempt_id,reason,status,version)` possui unique tenant/unidade/tentativa e no máximo uma tentativa ativa por unidade. Retry técnico mantém tentativa; refazimento autorizado incrementa tentativa sob lock da unidade. `operational_composition_snapshots` e linhas congelam instrução, versões, unidades e quantidades por revisão, com unique tenant/unidade/revisão. A tentativa referencia snapshot imutável; relacionar snapshot CMV comercial existente para conciliação sem sobrescrevê-lo. Para transformação em lote, `preparation_executions` referencia a ordem e sequência parcial unique tenant/ordem/execução, receita/rendimento e operação. Todos esses vínculos têm FKs compostas tenant/ID.

Saldo por lote/local deriva dos movimentos identificados. Movimentos legados sem lote permanecem identificados como origem legada; não inventar lote, validade ou rastreabilidade histórica. Um inventário físico conciliado pode estabelecer o saldo inicial rastreável, com operação e evidência explícitas.

Reservas persistentes, caso aprovadas, usam entidade própria vinculada à execução e expiração; `disponível = físico utilizável - reservado`. Lock temporário não é reserva persistente. Eventos duráveis devem estender infraestrutura compartilhada disponível ou introduzir infraestrutura transversal aprovada, sem fila de estoque paralela.

### Estados propostos e invariantes de transição

| Entidade | Estados persistidos e transições |
| --- | --- |
| Documento | `uploaded → processing → review_required → approved`; processamento pode ir a `failed`, com retry auditado para `processing`; documento anterior à aprovação pode ir a `rejected`; aprovado não volta a rascunho e correção gera revisão vinculada |
| Recebimento | `draft → ready → confirmed`; `draft/ready → cancelled`; edição de `ready` retorna a `draft`; confirmado só é corrigido por operação compensatória, sem apagar confirmação |
| Operação | `pending → committed` na unidade transacional; falha antes do commit faz rollback completo e não deixa efeito físico. Estado externo `failed` só para intenção/job persistido separado; não simular commit parcial |
| Extração/job | `queued → running → succeeded/failed`; retry preserva origem e registra nova tentativa de extração, sem duplicar documento |
| Vínculo financeiro | `not_requested → pending → linked`; `pending → error → pending`; `linked` só se altera por conciliação/estorno financeiro autorizado |
| Lote | `available ↔ blocked/quarantine` por autorização e motivo; `available → consumed/discarded` conforme saldo/operação; vencimento é condição calculada e não pode ser desbloqueado por mudança de rótulo |

`ready` exige referência tenant válida, conversão confirmada, somatório dos lotes igual à quantidade aceita e campos obrigatórios completos. `approved` exige documento conferido, identidades válidas e nenhuma pendência crítica; não gera movimento. Cancelar documento já relacionado a recebimento/título requer fluxo de compensação com vínculos, não simples transição para `rejected`. Toda transição valida versão e condições no servidor.

O comando `/receipts/{id}/confirm` aceita `draft` completo ou `ready`: no primeiro caso valida a passagem lógica por `ready` e confirma na mesma transação, sem exigir endpoint extra. Incompleto permanece sem efeitos físicos e retorna 422. O exemplo da seção 5 utiliza esse caminho.

Tipos comuns propostos: IDs String opacos; `version/sequence/number` Integer positivo; flags Boolean; quantidades/valores Decimal serializados como string; estados enums fechados; motivos String de tamanho limitado; observações Text; evidência estruturada JSONB sem substituir FKs. `unit_id` sempre referencia `inventory_units`. Nenhum número de documento ou GTIN é Integer, para preservar zeros iniciais. Datas de fabricação ausentes ficam null. Origem fiscal exige unidade/quantidade original e não apenas normalizada.

## 4. Convenções dos contratos propostos

Base nova definida nesta Fase 0 para implementação futura: `/api/gestao/inventory/v1`. Não existe publicação desses endpoints nesta fase. Contratos existentes em `/api/gestao/inventory/...` permanecem intactos. Nenhum alias novo sem `/api` é necessário. A integração frontend usará o resolvedor atual de `client/lib/api.ts`.

- Sucesso novo segue DTO direto do domínio inventory; lista paginada `{ "items": [], "next_cursor": null }`. Não envolver os endpoints publicados em `success/data`.
- Erro de domínio segue `err(DomainError)` real: `{ "success": false, "error": { "code": "ReceiptVersionConflict", "message": "..." } }`. Cada nova subclasse define `http_status` e chama `DomainError(message, code=...)`; não usar assinatura fictícia de construtor com status posicional.
- Autenticação/autorização e validação Pydantic podem retornar `detail`, conforme handlers/dependências existentes; não prometer formato único sem implementar compatibilidade. Exemplos de domínio não representam todos os erros HTTP.
- HTTP: 201 criação; 200 consulta/comando concluído; 202 processamento assíncrono persistido; 404 referência inexistente no escopo; 409 conflito de versão/idempotência/estado; 422 regra/quantidade/unidade inválida; 403 permissão insuficiente. Não expor existência de IDs de outro tenant.
- IDs são opacos. Datas: `YYYY-MM-DD`; instantes ISO 8601 com offset, persistidos com fuso. Datas sanitárias obedecem o fuso operacional configurado, sem presumir meia-noite UTC.
- Decimais novos via strings canônicas com ponto (`"40.000000"`), sem notação exponencial/NaN/infinito. DTOs explicitamente serializam Decimal; `jsonable_encoder` sozinho não garante esse contrato.
- Comandos físicos e financeiros exigem `Idempotency-Key`; revisões exigem `expected_version`. Nenhum payload escolhe tenant/ator. Essas identidades vêm do contexto confiável.
- Campo ausente e `null` são diferentes em PATCH; confirmação rejeita campos críticos pendentes. Parâmetros desconhecidos de comando devem ser rejeitados para não esconder erro de integração.

### Matriz de operações propostas

| Método/recurso sob a base nova | Entrada/saída essencial | Efeito e autorização |
| --- | --- | --- |
| POST `/documents` | upload multipart + compra opcional → documento/job | Persiste arquivo privado e extração pendente; `inventory/create`; não movimenta |
| GET `/documents/{id}` | dados originais/conferidos, status, pendências e versão | `inventory/view`; dados fiscais/custos conforme permissão adicional |
| PATCH `/documents/{id}` | versão e correções por campo/linha | `inventory/edit`; mantém evidência anterior |
| POST `/documents/{id}/approve` | versão e associações/conversões/parcelas conferidas | `inventory/manage`; não implica recebimento físico nem pagamento |
| POST `/receipts` | documento/compra, linhas, lotes e revisão → rascunho | `inventory/create`; sem efeito em saldo |
| POST `/receipts/{id}/confirm` | versão, conferência final → operação/movimentos | `inventory/manage`; entrada física atômica |
| GET `/lots` | item/local/estado/validade/cursor | `inventory/view`; sem custo no DTO operacional |
| POST `/lots/{id}/open` | versão, abertura, recipiente, regra cadastrada | `inventory/edit`; validade efetiva recalculada e auditada |
| POST `/lots/{id}/block` | versão, motivo → lote bloqueado | `inventory/manage`; conciliar reservas/execuções afetadas |
| POST `/conversions/preview` | insumo, embalagem/revisão, quantidade/peso aferido | `inventory/view`; cálculo puro, sem saldo |
| POST `/compositions/preview` | seleção comercial e quantidade → composição/pendências | leitura autorizada do catálogo/receita; custos só com `cmv/view` |
| GET `/operations/{id}` | resultado persistido e rastreio autorizado | `inventory/view`; reconsulta segura após timeout |
| POST `/documents/{id}/payables/reconcile` | parcelas e títulos já existentes → vínculos/pendências | `financeiro/manage` e escopo autorizado do documento; geração financeira idempotente |

Consumo de produção deve ser contrato interno da transição KDS autorizada, não endpoint público que aceite status/quantidade arbitrários. A futura API de execução pertence ao contrato KDS e chama o mesmo service transacional de estoque.

## 5. Exemplos executáveis como especificação

IDs são ilustrativos. Exemplos são propostas, não chamadas que funcionam hoje.

### Conversão de 10 peças aferidas como 40 kg

`POST /api/gestao/inventory/v1/conversions/preview`

```json
{"inventory_item_id":"insumo-mucarela","packaging_id":"embalagem-peca","packaging_version":2,"commercial_quantity":"10","commercial_unit_id":"un-peca","measured_base_quantity":"40.000000","base_unit_id":"un-kg"}
```

HTTP 200, DTO direto:

```json
{"inventory_item_id":"insumo-mucarela","original_quantity":"10","original_unit_id":"un-peca","base_quantity":"40.000000","base_unit_id":"un-kg","effective_factor":"4.000000000000","factor_source":"measured","packaging_version":2,"requires_review":false}
```

Peso variável exige aferição; não reutilizar fator médio de outra entrega como peso real. Para 12 refrigerantes de 2 L, estoque comercial pode ser 12 unidades e volume informativo 24 L: um único item com unidade base definida; não creditar dois saldos pelo mesmo recebimento.

### Recebimento conferido

`POST /api/gestao/inventory/v1/receipts`, header `Idempotency-Key: receipt-doc-42-part-1`:

```json
{"document_id":"doc-42","purchase_id":"compra-9","sequence":1,"lines":[{"document_line_id":"docline-1","inventory_item_id":"insumo-mucarela","commercial_quantity":"10","commercial_unit_id":"un-peca","packaging_id":"embalagem-peca","packaging_version":2,"measured_base_quantity":"40.000000","base_unit_id":"un-kg","location_id":"camara-1","lots":[{"supplier_lot_code":"FAB-001","quantity":"40.000000","manufactured_on":null,"expires_on":"2026-11-15"}]}]}
```

HTTP 201:

```json
{"id":"receipt-1","status":"draft","version":1,"document_id":"doc-42","pending_fields":[],"lines":[{"id":"receipt-line-1","base_quantity":"40.000000","base_unit_id":"un-kg"}]}
```

`POST /api/gestao/inventory/v1/receipts/receipt-1/confirm`, header `Idempotency-Key: confirm-receipt-1`, body `{"expected_version":1}`:

```json
{"id":"receipt-1","status":"confirmed","version":2,"operation_id":"operation-1","movement_ids":["movement-1"],"lot_ids":["lot-1"],"financial_status":"not_requested"}
```

HTTP 200. O service busca custo conferido no documento, calcula rateios autorizados e congela custo na operação; não aceita custo livre no comando de confirmação. Sem documento fiscal, entrada manual continua identificada como tal e exige os campos de custo/motivo previstos no fluxo autorizado.

Conflito HTTP 409:

```json
{"success":false,"error":{"code":"ReceiptVersionConflict","message":"O recebimento foi alterado. Atualize os dados antes de confirmar."}}
```

### Composição operacional

`POST /api/gestao/inventory/v1/compositions/preview`:

```json
{"product_id":"pizza-base","quantity":2,"selected_size_id":"tamanho-grande","flavors":[{"product_id":"sabor-a","position":0},{"product_id":"sabor-b","position":1}],"add_ons":[]}
```

HTTP 200 sem autorização de custos:

```json
{"complete":true,"recipe_version_ids":["ficha-a-v3","ficha-b-v2","ficha-base-v1"],"ingredients":[{"inventory_item_id":"insumo-mucarela","quantity":"0.300000","unit_id":"un-kg"},{"inventory_item_id":"insumo-calabresa","quantity":"0.200000","unit_id":"un-kg"},{"inventory_item_id":"embalagem-caixa","quantity":"2.000000","unit_id":"un-unidade"}],"missing":[]}
```

Exemplo pressupõe ficha de meia pizza A com 0,150 kg, B com 0,100 kg e embalagem de uma unidade por pizza, sem desperdício. É regra matemática ilustrativa, não gramagem comercial aprovada. Não devolver `unit_cost`, custo total, fornecedor ou saldo nesse DTO.

### Parcelas do documento

`POST /api/gestao/inventory/v1/documents/doc-42/payables/reconcile`, `Idempotency-Key: payables-doc-42-v1`:

```json
{"expected_version":3,"installments":[{"number":1,"due_date":"2026-11-01","amount":"400.00"},{"number":2,"due_date":"2026-12-01","amount":"400.00"}],"existing_transaction_ids":[]}
```

HTTP 200:

```json
{"document_id":"doc-42","status":"linked","transaction_ids":["fin-trx-1","fin-trx-2"],"obligation_total":"800.00","paid_total":"0.00"}
```

Vencimentos provêm da conferência, não da previsão de chegada da compra. Parcelas somam a obrigação conferida. Se a compra já gerou título, reconciliar o título existente; conflito exige resolução autorizada e não cria dívida duplicada. Este comando não registra pagamento.

## 6. Composição e consumo

Fórmula canônica: `quantidade normalizada da linha × fração ocupada / fração de referência × quantidade comercial`, seguida da política explícita de perda. Preservar inicialmente a semântica existente `1 + waste_percent/100`; percentual de desperdício sobre insumo e rendimento percentual são conceitos diferentes e não intercambiáveis.

Ficha sabor referência 0,5: inteiro 2×, dois sabores 1× cada, três sabores 2/3× cada. Base, embalagem e componente por pizza têm referência 1 e são aplicados uma vez por unidade; adicionais, massas e bordas dependem da seleção existente. Nunca transformar observação livre em gramagem/removal automaticamente.

Usar frações racionais ou Decimal com precisão de cálculo superior à persistida; distribuir resíduo determinístico na última alocação para soma exata. Fichas antigas com referência 1 mantêm suas quantidades até revisão humana; não converter todas para 0,5 por migration automática. Tamanho secundário hoje depende de correspondência por rótulo no motor; evolução para equivalência estável exige mapping explícito e testes de compatibilidade.

Snapshot existente é composição/custo teórico congelado. Consumo físico novo referencia snapshot e versões, mas grava execução, lotes, quantidades e custo efetivos separadamente. Alterar ficha ou custo posterior não reescreve nenhum dos históricos. Se não existe snapshot legado, resolver explicitamente a composição usada antes do consumo e persistir a evidência; não depender de receita ativa mutável durante retry.

O snapshot operacional/revisão de composição deve existir antes de exibir instrução executável, reservar ou iniciar tentativa. A tentativa referencia essa revisão: gramagens exibidas, reserva e baixa não podem resolver versões diferentes de receita. Prévia administrativa é identificada como simulação sem autorização de execução. Se seleção comercial mudar, invalidar a prévia e criar revisão/tentativa explícita conforme estado permitido, sem alterar execução iniciada.

Contrato interno proposto: `consume_execution(actor, execution_id, expected_version, snapshot_id)` retorna operação e alocações. O service deriva pedido, item/unidade e quantidades do banco. Produção inicial, produção parcial e refazimento possuem execuções distintas. A transição para `preparing` atual continua sendo a única autoridade de baixa até corte controlado; não executar baixa legada e nova simultaneamente.

Preparação transforma insumos em um `inventory_item` preparado: débito dos lotes de origem + crédito do lote produzido na mesma operação. Venda que usa preparado consome o preparado; não baixa novamente seus ingredientes. Grafo de composição rejeita ciclos. Saída registra rendimento real e perdas; completar parcialmente uma ordem gera execução explícita, não repetição da mesma conclusão.

## 7. Idempotência e limites transacionais

| Ação | Identidade de negócio, além da chave HTTP | Transação mínima |
| --- | --- | --- |
| Importar documento | tenant/chave fiscal; fallback normalizado fornecedor+número+série+tipo | documento + identidade + extração pendente; arquivo reconciliado |
| Confirmar recebimento | tenant/recebimento/confirmar | versão + linhas + lotes + movimentos + resultado da operação |
| Abrir recipiente | tenant/recipiente/evento de abertura | versão + evento + validade resultante |
| Produzir preparo | tenant/execução preparo/conclusão | débito origem + crédito saída + rendimento + genealogia |
| Consumir pedido | tenant/execução produção/consumo | status/versão + snapshot + alocação FEFO + movimentos + operação |
| Refazer | tenant/nova execução/refazimento | autorização/motivo + consumo próprio; nunca reutilizar execução inicial |
| Gerar obrigação | tenant/documento/parcela/natureza | título existente ou novo + vínculo + resultado idempotente |
| Compensar movimento | tenant/operação origem/compensação autorizada | limites acumulados + movimentos inversos + auditoria |

Chave HTTP tem escopo tenant + método/recurso normalizado. Persistir hash canônico de entrada e resultado no mesmo commit do efeito. Mesma chave/mesmo conteúdo retorna resultado original; conteúdo diferente retorna 409. Chaves distintas com mesma identidade de negócio não duplicam efeitos. Reautorizar cada replay para não vazar resposta a usuário sem acesso. Reprocessamento de extração não confirma novamente documento ou recebimento.

A identidade física/financeira de negócio permanece pelo período de conservação do histórico, independentemente de expiração/limpeza do cache HTTP de idempotência. TTL de replay não libera nova baixa, entrada, conclusão ou obrigação da mesma origem.

Ordem de lock proposta: entidade de negócio/execução → insumos ordenados por ID → lotes ordenados por validade efetiva, recebimento e ID. Revalidar saldo utilizável após locks. Todos os escritores físicos adotam o mesmo protocolo. FEFO estrito não usa `SKIP LOCKED` para pular silenciosamente lote prioritário; conflito espera por limite configurado ou retorna retry seguro. Deadlock/serialization failure permite retry interno limitado da transação inteira antes do efeito externo, com identidade preservada.

Services internos de uma operação usam flush e não fazem commit isolado. O application service é dono do único commit. Métodos existentes que fazem commit precisam ser adaptados explicitamente, preservando contratos, antes de participar da unidade transacional nova.

Recebimento físico e obrigação financeira podem concluir em transações separadas, com estado explícito de sincronização e evento durável/reconciliação. Falha financeira não pode fingir reversão física nem desaparecer em `except: pass`. Não gerar título por recebimento parcial quando a dívida já é do documento integral. Nunca efetuar pagamento como efeito da entrada de estoque.

Uploads, OCR e integrações externas ficam fora da transação de locks físicos. Job persistido e resultado de extração são reexecutáveis; arquivo privado pode exigir reconciliação de órfãos. Mensagem/notificação ocorre após commit via entrega durável. Timeout do cliente exige consulta de operação; frontend não repete mutação com chave nova.

## 8. Lotes, validade e cancelamento

Saldo físico, saldo utilizável e reserva são projeções diferentes. Estado armazenado do lote: disponível/bloqueado/quarentena/consumido/descartado; proximidade de vencimento e vencimento podem ser projeções calculadas no instante da consulta. A verificação de consumo sempre reavalia validade, mesmo que um job de alerta esteja atrasado.

FEFO: lotes utilizáveis por menor validade efetiva, depois recebimento e ID. Lote sem validade depende da política cadastrada do item; não ordenar como utilizável sem regra. Validade efetiva considera menor limite aplicável de origem, abertura e regra validada. Transformação não amplia prazo indevidamente; decisões sanitárias cabem ao responsável competente e gestor.

Antes de produção: liberar reserva existente, sem entrada fictícia. Depois de consumo: cancelar pedido não devolve material automaticamente; manter consumo e registrar perda auditável. A perda pós-consumo não baixa novamente a mesma quantidade. Retorno físico recuperável exige inspeção, autorização e operação própria com vínculo à origem; soma de retornos não supera o consumido recuperável. Refazimento cria nova execução e novo consumo, sem apagar perda original.

## 9. Decimal e compatibilidade

Proposta técnica inicial: quantidades `NUMERIC(20,6)`, custo unitário `NUMERIC(20,8)`, fatores `NUMERIC(24,12)`, dinheiro liquidável `NUMERIC(20,2)`. Validar amplitude/escala com dados reais e XML antes de fixar migration; documentos podem exigir precisão intermediária maior. Cálculos mantêm precisão ampliada e arredondam somente em fronteiras declaradas. Modo de arredondamento monetário depende da política aprovada; não escolher silenciosamente.

Sequência futura: inventariar Float/serializadores → definir unidades/escala → ensaiar conversão em clone descartável → medir resíduos e reconciliar somas → migration expansiva com validação → corte único de escrita → adapter de leitura legado → endurecer constraints após aceite. `Decimal(str(float_legado))` evita novos artefatos de conversão binária, mas não recupera precisão já perdida; não prometer reparação histórica automática.

Campos JSON dos endpoints publicados continuam com tipos publicados; novos endpoints usam strings decimais. Não manter duas quantidades editáveis como verdades paralelas. Se colunas de transição forem necessárias, definir uma autoridade de escrita por etapa, invariantes e remoção. Relatórios históricos e snapshots antigos não são reprecificados. Mudanças no financeiro/fiscal exigem auditoria dos consumidores além do inventário.

## 10. Tenant, RBAC e privacidade

Reutilizar `require_rbac_permission(module_key, permission_key)` e `AuthorizedTenantActor`; módulos reais `inventory`, `cmv`, `financeiro`, `cozinha`. Permissões existentes `view/create/edit/manage/export` devem ser concedidas pelo modelo atual, sem segundo sistema de papéis. `approve` não existe como permissão assumida: comandos sensíveis usam `manage` até eventual evolução explícita aprovada.

Tenant/usuário sempre do contexto confiável; filtros de leitura, locks, childs, jobs, hashes/identidades e armazenamento incluem tenant. Payload com tenant não muda escopo. Suporte usa fluxo de suporte existente auditável. Compatibilidade legada do resolvedor atual não autoriza novas entidades sem proprietário definido. Conta de estação KDS é restrita à própria estação no mecanismo atual: leitura operacional da ficha deve ser exposta pelo contrato da estação autorizada, não concedendo acesso geral a `inventory`.

DTO operacional de composição exclui custo, margem, fornecedor, notas fiscais, contas a pagar e saldo global. Dados de custo exigem `cmv/view`; documentos/parcelas exigem permissão financeira conforme operação. Resposta não pode carregar campos privados e depender do frontend para ocultá-los. Arquivo fiscal tem download autorizado por tenant, sem URL pública reutilizável.

Uploads exigem limite de tamanho/páginas, tipo real, nome normalizado e parser XML seguro sem entidades externas; OCR externo depende de provedor, retenção e tratamento de dados aprovados. Campos ausentes ficam pendentes. Nenhum extrator inventa CNPJ, chave, lote ou validade. Conferência registra diferença, autor e evidência de origem.

## 11. Critérios verificáveis para próximas fases

1. Duas confirmações simultâneas com mesma origem geram uma única operação; mesma chave com payload diferente retorna 409 e zero efeito extra.
2. Dois pedidos competindo pelo último saldo não produzem saldo utilizável negativo; teste real PostgreSQL com conexões independentes.
3. Recebimento parcial repetido não duplica lote, saldo ou dívida; título antigo da compra é conciliado.
4. Conversão 10 peças aferidas em 40 kg gera exatamente 40 kg; 12 garrafas geram 12 unidades, preservando 24 L informativos.
5. Ficha meia/inteira/dois/três sabores e repetição de slots preservam fórmula; base/caixa não multiplicam por sabores; remoção estruturada não vem de texto livre.
6. Lote vencido/bloqueado/quarentena nunca é alocado; abertura parcial não reduz validade de recipientes fechados; genealogia permite localizar consumo por lote.
7. Transformação debita matéria-prima e credita preparado atomicamente; venda não duplica consumo da matéria-prima; falha intermediária deixa zero efeito parcial.
8. Cancelamento pós-consumo registra perda sem nova baixa ou devolução automática; refazimento tem execução própria; compensações têm teto auditável.
9. Operador KDS consulta composição sem custo/financeiro; IDs de outro tenant não são acessíveis, inclusive via replay, arquivo, job e exportação.
10. Snapshot legado mantém composição/custo teórico; consumo novo evidencia custo/lote reais; estoque ativo pode congelar composição mesmo com dashboard CMV desabilitado.
11. Decimal reconcilia quantidades e dinheiro conforme tolerância aprovada; contratos antigos mantêm tipos; indisponibilidade do financeiro fica visível e recuperável.
12. Build, testes apropriados, schema em clone, regressões catálogo/checkout/KDS/expedição e gates de deploy são evidências futuras; não foram executados nesta fase documental.

## 12. Decisões pendentes do gestor e gates

| Decisão de negócio pendente | Regra técnica segura até definição | Bloqueia |
| --- | --- | --- |
| Evento de compromisso físico por pedido/item/unidade e entrada em fila | preservar baixa atual em `preparing`; nenhuma segunda baixa | ativar consumo por execução e produção parcial |
| Reserva: evento, duração, expiração e tratamento de pagamento tardio | não chamar lock de reserva nem prometer estoque reservado | disponibilidade garantida entre checkout e produção |
| Política de custo, frete/desconto/tributos e arredondamento | manter histórico e identificar média atual sem reclassificá-la | custo real/CMV novo e migração monetária definitiva |
| Aceite de divergência, entrega parcial e excesso recebido | exigir conferência e bloquear excesso sem aprovação | recebimento automático |
| Obrigação por documento/compra, crédito/devolução e conciliação de título antigo | não gerar nova dívida se houver obrigação vinculada pendente de revisão | automação financeira |
| Prazo sanitário por item/preparo/abertura e lote sem validade | não inventar validade nem liberar lote sem regra | FEFO/preparo de itens afetados |
| Receita sem ficha versus ficha parcial, adicionais/removíveis/substituições | preservar compatibilidade antiga; impedir baixa parcialmente calculada | ativação por família de produto |
| Alçadas de aprovação, perdas, retorno recuperável e refazimento | usar permissões existentes e exigir motivo; não devolver consumo automaticamente | automações sensíveis |
| Provedor OCR, retenção e revisão humana | XML/texto primeiro; OCR só rascunho | uso externo de imagens/documentos |

**Gate arquitetural:** implementar somente após aprovação das fases seguintes, usando as decisões F0 de receita de preparo, unidade/tentativa e compatibilidade Decimal; revisar a infraestrutura transversal de eventos duráveis no plano técnico da fase correspondente. **Gate de dados:** clone descartável com revision real e ensaio reconciliado antes de migration em produção. **Gate de ativação:** feature flags por tenant e critérios acima validados; não pressupor que a existência de uma migration local significa aplicação na VPS.

Esta Fase 0 entrega contratos revisáveis e dependências explícitas. Os contratos novos permanecem propostos até a aprovação das próximas fases e das regras pendentes correspondentes.
