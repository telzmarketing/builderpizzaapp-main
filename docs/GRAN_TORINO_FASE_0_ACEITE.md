# Gran Torino — Fase 0: requisitos, aceite e validação

Data da revisão: 2026-10-21. Responsáveis: Product Owner / QA-DevOps, sob coordenação do Orquestrador.

## 1. Objetivo, autorização e limites

Transformar o prompt master em requisitos rastreáveis, critérios verificáveis e gates de execução. Esta entrega é exclusivamente documental. Não implementa funcionalidades, não altera contratos, não executa testes/builds/migrations, não acessa banco e não faz deploy. Aprovar a documentação não equivale a autorizar automaticamente fases futuras ou a confirmar recomendações de negócio.

Escopo: os cinco módulos solicitados — estoque/entrada inteligente, fichas técnicas, Cozinha Preparo/PCP, consulta interativa KDS e distribuição KDS multioperador — e suas dependências de compras, financeiro, CMV, impressão, segurança e operação.

Fora do escopo: segundo catálogo/estoque/cadastro de usuários/RBAC, emissão fiscal refeita, compras efetivadas sem aprovação, IA para cálculos determinísticos, parâmetros sanitários inventados, alterações de produção e treinamento executado nesta fase.

## 2. Baseline e confiabilidade das evidências

HEAD observado: `4d553bf1e7678d65f22616b93c733fbb470afc2f`. A revisão é estática da árvore de trabalho, que já contém mudanças alheias em `.claude` e arquivos não rastreados de marketplace; esses itens não integram esta entrega. Nenhuma afirmação abaixo prova estado da VPS, revisão aplicada no banco, aprovação do CI ou funcionamento ponta a ponta. Documentação antiga é contexto, não comprovação atual. Head da fonte, mesmo quando determinado pela cadeia Alembic, não comprova banco atualizado.

| Ref. | Fonte real | Fato observável / limite |
|---|---|---|
| S1 | `backend/models/inventory.py`, `backend/services/inventory_service.py`, `backend/routes/inventory.py`, `backend/schemas/inventory.py` | Unidades, categorias, locais, fornecedores, insumos, compras, entradas manuais, movimentos e receitas existem. Não presume lotes/FEFO/PCP completos. Quantidades e custos ainda usam `Float`. |
| S2 | `backend/services/recipe_resolution.py`, `backend/services/cmv_snapshot_service.py`, `backend/models/cmv.py` | Reutilizar resolução e snapshots existentes; não criar motor paralelo. |
| S3 | `backend/models/product.py`, `backend/models/order.py`, `backend/services/order_service.py`, `client/pages/admin/Products.tsx` | Catálogo/pedido canônicos; integração preserva IDs e opções comerciais reais. |
| S4 | `backend/services/kds_service.py`, `backend/routes/kds.py`, `backend/core/kds_station_access.py`, `client/pages/admin/Cozinha.tsx`, `client/pages/admin/Expedicao.tsx`, `client/pages/admin/KdsOverview.tsx` | KDS/cozinha/expedição existentes não comprovam filas individuais ou distribuição inteligente. |
| S5 | `backend/models/finance.py`, `backend/services/finance_service.py`, `backend/services/fiscal_service.py`, `client/pages/admin/gestao/GestaoFinance.tsx`, `client/pages/admin/gestao/GestaoFiscal.tsx` | FinanceTransaction possui vínculo com compra de estoque; emissão fiscal a partir de pedido não é importação NF-e de fornecedor. Valores financeiros usam `Float`. |
| S6 | `client/lib/printing.ts`, `client/components/kds/LabelPrintDialog.tsx`, `docs/expedicao-etiquetas.md` | Infraestrutura de impressão reutilizável; impressão física e etiquetas de preparo não comprovadas nesta fase. |
| S7 | `tests/test_wave7_inventory_context.py`, `tests/test_wave7_finance_context.py`, `tests/test_rbac_tenant_routes.py`, `tests/test_tenant_upload_acl.py`, `tests/test_tenant_upload_namespace.py` | Contratos de tenant/RBAC/arquivos têm testes existentes; aprovação não foi executada agora. |
| S8 | `.github/workflows/deploy.yml`, `.github/workflows/prepare-manual-deploy.yml`, `scripts/deploy-telz-from-origin.sh`, `scripts/update-telz.sh`, `docs/UPDATE_TELZ_VPS.md` | Fluxo Telz imutável e gates operacionais existentes; conferir target efetivo nos arquivos da release futura. |
| S9 | `client/lib/api.ts`, `client/pages/admin/gestao/GestaoInventory.tsx`, `client/pages/admin/gestao/GestaoCmv.tsx`, `backend/services/cmv_service.py` | Caminhos oficiais de interface/API e CMV a preservar. |

Correção importante sobre material anterior: o código atual de `InventoryService.consume_order_sale` exige `preparing`; `reverse_order_sale` possui registro `order_sale_loss` sem recompor alimento produzido. `update_product_recipe` desativa versão anterior e publica nova. Não repetir como defeitos atuais afirmações incompatíveis de `docs/AUDITORIA_PRODUTOS_OPERACAO_2026-10-20.md`. Ainda é necessário validar lote, unidade física, tentativa e integração completa, que esses fatos isolados não comprovam.

## 3. Fases e gates usados na matriz

Os nomes abaixo representam dependências e correspondem à numeração aprovada do plano arquitetural consolidado. Não criam autorização de execução. F0 é esta baseline documental.

- **FUN / F1:** fundação: precisão, conversões, movimentos, reservas, lotes e concorrência.
- **COM / F2:** composição: evolução das receitas, opções e snapshots históricos.
- **ENT / F3:** entrada XML, conferência, recebimento e vínculo financeiro. **F9** complementa PDF, câmera e OCR.
- **RAS / F4:** rastreabilidade: abertura, validade, FEFO, genealogia e etiquetas.
- **PCP / F5:** receitas intermediárias, execução e transformação. **F8** acrescenta planejamento, previsão, capacidade e agendamento.
- **KCI / F6:** KDS consulta interativa sobre composição oficial.
- **KMO / F7:** KDS multioperador e unidade/tentativa, inicialmente atribuição por pedido; granularidade por pizza em ativação posterior.
- **GER / F10:** fechamento consolidado, custos/CMV, dashboards e alertas; sugestões de reposição entram em **F8**, junto ao planejamento.

Contratos de consumo/unidade/tentativa são definidos desde F0 e fundados em F1/F2; a implementação operacional completa da unidade/tentativa e corte dos escritores ocorre em F7. Execução PCP F5 precisa de identidade própria de transformação, não pode aguardar F7 para ser idempotente.

Gates: **G1** contrato/modelagem aprovado antes de programar; **G2** teste automatizado determinístico e integração PostgreSQL; **G3** teste de interface e fluxo integrado; **G4** piloto real autorizado com observação/reconciliação. Cada requisito só fica concluído depois dos gates indicados; mapear um teste existente não significa que ele cubra toda extensão proposta.

## 4. Requisitos e aceite rastreável

Situação: **E** existe base reutilizável, **P** parcial e exige evolução, **N** capacidade nova proposta. As situações descrevem a capacidade solicitada, não sua aprovação em produção. Prioridades: **P0** integridade/segurança e dependências bloqueantes; **P1** operação principal; **P2** evolução gerencial/automação avançada. Todos os cinco módulos possuem funcionalidades P1; P2 não exclui o requisito do escopo final.

### 4.1 Estoque e entrada inteligente

| ID / prioridade | Requisito e aceite objetivo | Fonte / situação | Fase | Teste e gate |
|---|---|---|---|---|
| EST01 P0 | Reutilizar insumo/unidade/local/fornecedor: importar ou editar mantém IDs oficiais; não cria duplicatas por descrição equivalente. | S1 E/P | FUN/ENT | Integração cadastro/recebimento + tenant; G1/G2/G3 |
| EST02 P0 | Quantidades/custos críticos Decimal/NUMERIC com escala definida: soma, conversão e rateio conciliam, sem passagem por float no cálculo novo; migração mantém tolerância/reconciliação aprovada. | S1/S5 P | FUN | Fixtures de legado, extremos, arredondamento, schema; G1/G2 |
| EST03 P0 | Conversão dimensional compartilhada: 10 peças de 4 kg = 40 kg; preservar original/fator; peso variável exige conferência; massa→volume sem densidade é rejeitada. | S1 P | FUN | kg/g/mg, L/mL, caixas/fardos, inválidas/reversíveis; G1/G2/G3 |
| EST04 P1 | XML estruturado antes de texto PDF e OCR: cada campo tem origem e pendência/confiança; documento ilegível não inventa dados nem atualiza saldo. Captura câmera usa o mesmo fluxo de upload. | S5/S7 N | F3 XML; F9 PDF/câmera/OCR | XML/PDF/JPG/PNG/câmera, malformados/ilegíveis; G1/G2/G3 |
| EST05 P0 | Identificar duplicidade por tenant/chave fiscal e identidade alternativa revisada: duas confirmações concorrentes/retry geram um conjunto de movimentos; reprocessar rascunho não duplica entrada confirmada. | S1/S5 P | ENT | Corrida real PG e falha após confirmação; G1/G2/G3 |
| EST06 P1 | Reconhecimento por GTIN/código do fornecedor, embalagem e histórico; associação incerta exige confirmação; associação confirmada é reutilizada sem criar insumo automaticamente. | S1 N | ENT | Variações de descrição, embalagens/fornecedores distintos; G1/G2/G3 |
| EST07 P0 | Conferência e aprovação registram quantidade aceita/rejeitada/pendente, responsável, documento e múltiplos lotes; recebimento parcial não confirma mercadoria não recebida. | S1 P | ENT/RAS | Parcial, divergência, retry, falha no commit; G1/G2/G3/G4 |
| EST08 P0 | Saldo disponível separa físico, reservas e indisponível; dois consumos concorrentes não superam disponível; movimento mantém origem e reconciliação. Estoque legado sem lote tem política explícita de transição. | S1 P | FUN/RAS | Saldo agregado e corrida por item/local/lote; G1/G2/G4 |
| EST09 P0 | FEFO só escolhe lotes elegíveis; vencido/bloqueado/quarentena não reserva nem consome; validade após abertura respeita menor limite aplicável e regra cadastrada. Ausência de validade segue política aprovada. | S1 N | RAS | Múltiplos lotes, empate, vencimento limite, abertura parcial; G1/G2/G3/G4 |
| EST10 P0 | Nota recebida vincula obrigação existente sem duplicar conta/parcelas; ausência de vencimento fica pendente; entrada física não cria pagamento nem obrigação inventada. | S1/S5 P | ENT/GER | Financeiro existente/novo/ausente, concorrência; G1/G2/G3 |
| EST11 P1 | Ajuste, inventário, transferência, devolução, perda e descarte mantêm histórico e permissão; contagem 12 contra teórico 13 gera divergência de 1, não sobrescrita silenciosa. | S1 P | FUN/RAS/GER | Auditoria e reconciliação por origem; G1/G2/G3/G4 |

### 4.2 Fichas técnicas e consumo

| ID / prioridade | Requisito e aceite objetivo | Fonte / situação | Fase | Teste e gate |
|---|---|---|---|---|
| FIC01 P0 | Vincular ficha a produto/tamanho/opções existentes, insumos oficiais e versão; produto legado sem ficha continua vendável conforme política atual configurada. | S1/S2/S3 E/P | COM | `test_product_recipe_operations.py` + regressão catálogo; G1/G2/G3 |
| FIC02 P0 | Motor único: 150 g por meia pizza resulta 300 g inteira, 150 g na metade e 100 g no terço; frações reais e sabores repetidos determinam soma; quantidade vendida multiplica unidades. | S2 E/P | COM | Testes de fração existentes + precisão Decimal; G1/G2 |
| FIC03 P0 | Base/massa/molho comum/caixa aplicados uma vez por pizza; sabor, borda, adicional, remoção/substituição e alterações locais respeitam escopo; observação livre não inventa gramagem. | S2/S3 P | COM | Base única, 2/3 sabores, opções e falta de ficha; G1/G2/G3 |
| FIC04 P1 | Editor administrativo permite ordem/método/instruções/imagem opcional; edição preserva versões e snapshot de produção anterior. | S1/S2/S3 P | COM | Versão anterior imutável, imagem ausente; G1/G2/G3 |
| FIC05 P0 | Endpoint público contém só ingredientes comerciais autorizados; não envia quantidades técnicas/custos/saldo/lotes/fornecedores, inclusive em campos aninhados. Operador vê técnica sem custo se não autorizado. | S3/S7 P | COM | Contratos públicos e RBAC negativo; G1/G2/G3 |
| FIC06 P0 | Consumo identifica unidade física e tentativa: retry não consome novamente; refazimento legítimo cria nova tentativa. Congelar versão de receita/custo em evento operacional definido. | S1/S2 P | FUN/COM/KMO | Idempotência/retrabalho/parcial/corrida PG; G1/G2/G4 |
| FIC07 P0 | Antes do uso cancelar libera reserva; após uso não devolve alimento; consumo parcial mantém o realizado e sua destinação. Momento único de consumo depende da decisão D1. | S1 P | FUN/COM/KMO | `test_pg_stock_only_preparing_idempotence_and_cancellation_loss` + tentativas; G1/G2/G4 |

### 4.3 Cozinha Preparo / PCP

| ID / prioridade | Requisito e aceite objetivo | Fonte / situação | Fase | Teste e gate |
|---|---|---|---|---|
| PCP01 P1 | Preparação referencia estoque oficial e receita versionada com rendimento, unidade, peso por porção, lote, tempos/descanso, validade, armazenamento, antecedência e instruções administráveis; impedir ciclos de preparações. | S1/S2 N | PCP | Grafo acíclico, rendimento/conversão; G1/G2/G3 |
| PCP02 P0 | Transformação é atômica e idempotente: 20 kg→40 porções de 300 g deixa 8 kg +40 porções; consumo de uma porção deixa 39 e mantém 8 kg bruto. Falha intermediária não persiste metade. | S1/S2 N | PCP | Fault injection e concorrência PG; G1/G2/G4 |
| PCP03 P0 | Registrar produção real aprovada, perdas/descarte e saldo pendente: 47 de 50 não inventa perda de 3; vários apontamentos parciais não ultrapassam ou duplicam a mesma execução. | S1 N | PCP | Parcial, excesso explícito, retry, perda motivada; G1/G2/G3/G4 |
| PCP04 P1 | Planejamento semanal por sabor/data/canal usa frações, promoções, ajustes/feriados, histórico e revisão; demanda promocional já incluída não é somada duas vezes. | S2/S3 N | F8 | Meio a meio, 3 sabores, combo, forecast inclusivo/aditivo; G1/G2/G3 |
| PCP05 P1 | Necessidade usa demanda + segurança − estoque elegível não reservado − produção confirmada aproveitável no período, evitando dupla dedução de reservas e dupla contagem de demanda; respeita validade futura, rendimento e embalagens. | S1/S2 N | F8 | Lote vence antes do uso, produção fora da janela, reserva existente; G1/G2/G3 |
| PCP06 P1 | Agendar conforme antecedência, dependências, capacidade e calendário; reprocessar não duplica ordem; revisão não apaga execução iniciada; aprovar/reprogramar/cancelar exige permissão e motivo. | S1/S7 N | F8 | Replanejamento concorrente e datas bloqueadas; G1/G2/G3/G4 |
| PCP07 P1 | Preparador tem tarefas agendadas/aguardando/em preparo/pausadas/parciais/concluídas/bloqueadas/canceladas, timestamps/autor e ficha digital; não edita parâmetros administrativos. | S4/S7 N | PCP | Estados legais, temporizadores e RBAC; G1/G2/G3/G4 |
| PCP08 P0 | Genealogia liga lotes de origem e saída; validade não se amplia indevidamente; etiqueta configura formato/cópias/campos e identidade do tenant. Reimprimir não movimenta estoque. | S6/S7 N | RAS/PCP | Origem→destino→pedido, reimpressão e impressora piloto; G1/G2/G3/G4 |
| PCP09 P1 | Fechamento reconcilia planejado/produzido/consumido/perdido/restante e contagem física; ajuste exige justificativa e saldo aproveitável alimenta dia seguinte. | S1/S9 N | PCP/GER | Exemplo 50−35−2=13; contagem 12 gera divergência 1; G1/G2/G3/G4 |

### 4.4 KDS interativo

| ID / prioridade | Requisito e aceite objetivo | Fonte / situação | Fase | Teste e gate |
|---|---|---|---|---|
| KCI01 P1 | Ação “Ingredientes e montagem” abre modal no card sem navegar, mudar status, atribuição, cronômetro ou fila; atualização em tempo real permanece ativa. | S4 N | KCI | Relógio controlado, abrir/fechar, evento enquanto modal aberto; G1/G2/G3/G4 |
| KCI02 P0 | Modal usa composição/snapshot oficial por unidade/tentativa e mostra sabores/frações/base/opções/remoções, quantidade, tamanho, operador, métodos e observações. | S2/S4 P | COM/KCI | Fixture de 1/2/3 sabores, receitas versionadas e opções; G1/G2/G3 |
| KCI03 P1 | Falha de receita/rede ou imagem opcional indisponível mostra mensagem e permite fechar/retry sem bloquear pedido ou reiniciar produção. | S4/S7 N | KCI | Timeout/403/404/imagem ausente, preservação estado; G1/G2/G3 |

### 4.5 KDS multioperador

| ID / prioridade | Requisito e aceite objetivo | Fonte / situação | Fase | Teste e gate |
|---|---|---|---|---|
| KMO01 P0 | Reutilizar usuário/sessão/RBAC; login não implica disponibilidade; presença explícita representa offline/disponível/produção/ocupado com fila/pausa sem limite fixo de profissionais. | S4/S7 P | KMO | Autenticado indisponível, heartbeat/reconexão, 2/5/mais operadores; G1/G2/G3 |
| KMO02 P1 | Backend distribui a disponível com desempate determinístico; todos ocupados: menor tempo restante + carga total da fila, considerando prioridade, complexidade e capacidade; forno não ocupa montador automaticamente. | S4 N | KMO | Exemplo cargas 11/5/8 min escolhe 5; empate/sem disponível; G1/G2/G3/G4 |
| KMO03 P0 | Duas atribuições/inícios concorrentes têm um vencedor e conflito explícito; fila persiste e recuperação/reprocessamento não perde nem duplica tarefa. | S4 N | KMO | Múltiplos workers, falha pós-commit e reconciliação PG; G1/G2/G4 |
| KMO04 P1 | “Iniciar preparo” registra início real; concluir montagem libera próximo início e mantém forno/conferência/expedição separados; relógio deriva de timestamps persistidos. | S4 P | KMO | Reload/reconexão/pausa e máquina de estados; G1/G2/G3/G4 |
| KMO05 P0 | Redistribuição automática só de não iniciadas e mantém prioridade/auditoria; desconexão transitória não abandona execução; intervenção em iniciada depende de autorização e protocolo. | S4/S7 N | KMO | Pausa, reconexão, corrida de transferência/início; G1/G2/G3/G4 |
| KMO06 P0 | Padrão por pedido preserva vínculo das unidades; modo por pizza só com configuração autorizada. Expedição só libera após todas unidades necessárias prontas, inclusive refazimentos válidos. | S3/S4 N | KMO | Pedido 3 pizzas, 2 prontas não libera; quantidade >1 por item; G1/G2/G3/G4 |

### 4.6 Requisitos transversais

| ID / prioridade | Requisito e aceite objetivo | Fonte / situação | Fase | Teste e gate |
|---|---|---|---|---|
| TRA01 P0 | Tenant obrigatório no backend, FKs/uniqueness e arquivos/jobs/eventos: B não lê nem altera dados/arquivos de A; master plataforma não recebe implicitamente poderes operacionais de todo tenant. | S7 P | Todas | 2 tenants, ID forjado, job/evento contexto ausente; G1/G2/G3 |
| TRA02 P0 | Auditoria inclui autor/contexto, origem, antes/depois aplicável, motivo, timestamp e correlação; não registrar documento/credencial sensível em logs abertos. | S1/S4/S7 P | Todas | Receita, ajuste, aprovação, permissões, redistribuição; G1/G2/G3 |
| TRA03 P0 | Arquivos fiscais privados com tipo/tamanho e conteúdo verificados; XML sem entidades externas; evitar execução de conteúdo, traversal, URLs arbitrárias e leitura cross-tenant; retenção e terceiros exigem D5. | S7 P | ENT/KCI | MIME falso, XML malicioso, grande/ilegível, ACL; G1/G2/G3 |
| TRA04 P1 | Sugestão de compras considera demanda líquida, reserva, vencimento, compra/produção programada, lead time e embalagem; revisão não duplica sugestão nem efetiva compra sem aprovação. | S1/S5 P | F8 | Necessidade 18 kg −12=6 kg antes do ajuste de embalagem/segurança; G1/G2/G3 |
| TRA05 P0 | Custos preservam aquisição/transformação/consumo histórico e rateios aprovados; CMV operacional e financeiro têm definições explícitas e reconciliáveis. | S2/S5/S9 P | FUN/COM/GER | 40 kg/R$1480→R$37/kg; 300 g→R$11,10; perdas/rendimento; G1/G2/G3/G4 |
| TRA06 P2 | Dashboards únicos reconciliam movimentos/produção/filas/compras; alertas configuráveis deduplicam evento e respeitam tenant/destinatário; previsão versus realizado preserva revisão. | S4/S9 P | GER | Mesma origem→mesmo total; replay não repete alerta indevido; G1/G2/G3/G4 |
| TRA07 P0 | Catálogo, checkout, canais, promoções, pagamentos, salão, delivery, KDS/expedição, financeiro, compras e impressão existentes preservados; todas chamadas React pelo caminho oficial `client/lib/api.ts`. | S3/S4/S5/S6/S9 E/P | Todas | Regressão selecionada + jornada cliente/admin, G2/G3/G4 |

## 5. Plano de validação futura e PostgreSQL descartável

Nenhum comando de teste ou banco desta seção foi executado na Fase 0. QA registra ambiente, SHA, comandos exatos, dados não sensíveis, esperados/observados, pass/fail/skip e limites por gate. Testes novos da matriz são propostas, não arquivos já implementados.

### 5.1 Base automatizada existente

| Suíte real | Cobertura reutilizável / limite |
|---|---|
| `tests/test_product_recipe_operations.py` | Fração/meia pizza, base, opção incompleta, saldo agregado, preparação/idempotência/perda, versões/snapshot e concorrência PG; não prova FEFO, PCP ou multioperador. |
| `tests/test_product_order_options.py`, `tests/test_product_order_postgresql.py`, `tests/test_product_catalog_corrections.py` | Opções e fluxos comerciais; complementar com preparações/refazimento sem alterar contratos. |
| `tests/test_wave7_inventory_context.py`, `tests/test_wave7_finance_context.py`, `tests/test_rbac_tenant_routes.py` | Tenant/contexto/RBAC; novos objetos exigem casos próprios inclusive jobs/arquivos. |
| `tests/test_kds_kitchen_dispatch.py`, `tests/test_kds_overview.py` | Limites cozinha/expedição/entrega e contratos; distribuição proposta exige integração real. |
| `tests/test_dispatch_labels.py`, `client/lib/printing.spec.ts`, `client/lib/kds.spec.ts` | Contratos e formatação; não substituem etiqueta/impressora física. |
| `tests/test_tenant_upload_acl.py`, `tests/test_tenant_upload_namespace.py`, `tests/test_tenant_upload_asset_model_contract.py` | ACL e namespace de uploads a estender para documentos/imagens técnicos. |
| `tests/test_runtime_schema_contract.py`, `tests/test_runtime_schema_migration.py` | ORM/schema após Alembic; precisam de banco explicitamente configurado quando a fixture requer. |
| `tests/test_origin_deploy.py`, `tests/test_immutable_release_delivery.py`, `tests/test_manual_deploy_workflow.py` | Contratos de entrega; execução na VPS e HTTPS são evidências separadas. |

### 5.2 Protocolo de ensaio

1. Após autorização de implementação/validação da fase, provisionar PostgreSQL 15 descartável isolado, usuário sem acesso à produção e nome de banco identificável; confirmar host/porta/database antes de qualquer setup. Nunca reutilizar `backend/.env` ou URL produtiva por conveniência.
2. Separar: banco vazio para cadeia Alembic completa, banco de fixtures sintéticas para testes que criam/apagam tabelas, e clone descartável anonimizado para ensaio de migração/restore. Rever lifecycle de cada fixture antes de compartilhar banco; execução paralela pode exigir databases distintos.
3. Fixar Python 3.12, Node 22 e pnpm conforme workflow/lock da release. Registrar versões e SHA; resolver divergência antes de comparar resultados.
4. No banco de migrations, executar cadeia aprovada a partir de zero e do predecessor real ensaiado; verificar um head esperado, revisão efetiva, constraints/índices e queries ORM. Head correto e `SELECT 1` não bastam. Nenhum target Alembic deve ser copiado de documentação antiga sem conferir fonte e release.
5. Criar fixtures de dois tenants, operadores e papéis; produtos legado/completo/parcial, tamanhos/opções, receitas históricas, três lotes por insumo e documentos duplicados/ilegíveis. Simular concorrência com conexões/processos independentes, rollback e falha após commit.
6. Rodar unidades, integração PG, contratos públicos/privados e regressão; depois interface com API/PG real descartável. Build/typecheck não provam ausência de falhas de runtime. Registrar cronômetro, fila, saldo e movimentos antes/depois das ações.
7. Piloto autorizado verifica impressão física, balança/peso conferido se aplicável, operador real, fluxo de forno/expedição e reconciliação de abertura/fechamento. Não usar mutações produtivas como sondagem ou repetir mutação após timeout sem consulta de idempotência.
8. Guardar evidências sem segredos/dados pessoais; só remover bancos/artefatos descartáveis após validar alvos e política de retenção do ensaio.

### 5.3 Lacuna de CI e critério contra falso verde

`tests/test_product_recipe_operations.py` e `tests/test_product_order_postgresql.py` requerem `PRODUCT_AUDIT_DATABASE_URL`; sem ela executam `pytest.skip`. `tests/test_runtime_schema_contract.py` requer `RUNTIME_SCHEMA_TEST_DATABASE_URL`. Os workflows de deploy/manual configuram a segunda, mas nesta baseline não configuram a primeira, embora chamem pytest. Portanto CI verde não comprova os casos PG de receitas/pedidos.

**Ação proposta futura:** incluir variável explícita apontando somente ao database descartável correto em todos os jobs relevantes, inclusive validação de artefatos; revisar os lifecycles das fixtures e impedir que testes destrutivos compartilhem o banco do ensaio runtime/migrations. Adicionar gate que falhe se qualquer caso PG crítico esperado não for coletado/executado ou terminar skipped. Não basta verificar exit code 0 do pytest geral; comparar IDs esperados e relatório de resultados. A Fase 0 registra a lacuna, sem editar workflow.

## 6. Decisões de negócio pendentes

Todas abaixo permanecem **PENDENTES**. As recomendações são defaults propostos para avaliação, sem aprovação presumida. O gestor decide parâmetros reais; mecanismos técnicos, índices, locks e distribuição determinística pertencem ao Arquiteto, não devem ser transferidos ao gestor.

| ID | Contexto e alternativas / vantagens e impactos | Recomendação pendente | Bloqueia |
|---|---|---|---|
| D1 | Consumo no início real facilita reserva/controle, mas exige que ação signifique uso; concluir montagem conhece resultado, mas precisa registrar consumo de execução interrompida. Atual `preparing` não é sinônimo comprovado de cada unidade iniciada. | Reservar antes do uso e consumir por início explícito de unidade/tentativa, com apontamento/reconciliação de parcial/perda; gestor confirma aderência da rotina. Preservar comportamento atual até migração autorizada. | Ativação de novo consumo/PCP/KMO; não a documentação F0. |
| D2 | Receitas, rendimento, ficha faltante e validade: bloqueio indiscriminado interrompe legado; liberar sem sinal perde controle. Nenhum exemplo do prompt define gramagem ou prazo oficial. | Gestor/responsável técnico fornece receitas, porções e validade por armazenamento/abertura; manter produtos legado conforme política existente até revisão explícita, sinalizando falta e impedindo consumo técnico parcial inventado. Sem validade aplicável: pendência/quarentena na nova operação rastreada. | Ativar receitas e lotes/preparações específicas. |
| D3 | Rateio/custo: frete/desconto/tributo pode variar por natureza e orientação contábil; regra universal inventada distorce margem. | Formalizar política com responsável financeiro/contábil, custo histórico e arredondamento conciliado; não mudar CMV legado silenciosamente. | Migração/ativação de custo e integração financeira completa. |
| D4 | Piloto, capacidade/calendário, pausas, SLA e transferência de iniciada: automação agressiva pode perder contexto real; manual total reduz benefício. | Primeiro tenant/unidade e equipe definidos; por pedido inicialmente; transferir automaticamente somente não iniciadas; timeout/pausas e capacidade parametrizados com dados piloto; iniciada só intervenção autorizada. | Ativação de planejamento/distribuição e rollout. |
| D5 | OCR externo e retenção fiscal: serviço pago pode reduzir digitação, mas traz custo e envio de documento a terceiro; XML/texto local evita dependência inicial, mas não cobre fotos. | XML/texto primeiro; OCR externo só com provedor, orçamento, retenção e compartilhamento aprovados; dados incertos sempre conferidos. | Uso de terceiro e ativação de OCR externo, não XML interno. |

Modalidade inicial por pedido, revisão humana de correspondência incerta, não compra automática e não redistribuição automática de iniciadas já são exigências do prompt. Não são novas dúvidas bloqueantes para F0.

## 7. Riscos e mitigação verificável

| Risco | Mitigação / prova exigida antes de ativar |
|---|---|
| Duplicar estoque bruto/preparado ou repetir consumo | Origem única, transformação atômica, unidade/tentativa e corrida PG; EST05/PCP02/FIC06. |
| Migração decimal com diferença histórica ou bloqueio prolongado | Expansão, backfill em lotes, reconciliação por origem e política de tolerância; ensaio em clone e compatibilidade entre releases; EST02/TRA05. |
| Legado sem lote/validade/receita | Política explícita de transição, não inventar origem ou prazos, flags e piloto; EST08/EST09/FIC01/D2. |
| Descompasso KDS, consumo e pedido | Transições oficiais e snapshot único; testar parcial/refazimento e agregação antes da expedição; FIC06/KMO06. |
| Concorrência, perda/repetição de evento e fila | Lock/constraints/idempotência definidos pelo Arquiteto, publicação confiável e reconciliação; falha antes/depois do commit; KMO03. |
| Receita/custo ou documento expostos entre papéis/tenants | Schemas restritos e autorização backend; ACL arquivo/job/evento; FIC05/TRA01/TRA03. |
| Erro OCR, associação/unidade ou dado fiscal inventado | Precedência XML, revisão humana e estado pendente; EST03/EST04/EST06. |
| Obrigação financeira ou previsão duplicada | Vínculos/documento e composição de demanda explícitos, revisão idempotente; EST10/PCP04/TRA04. |
| CI verde com casos críticos ignorados | Manifesto de testes PG esperados, URLs descartáveis explícitas e bloqueio de skips; seção 5.3. |
| Aplicar procedimento operacional legado | Conferir scripts/release Telz e runbook atual; sem pull/installer como updater; seção 8. |

## 8. Protocolo de deploy futuro e recuperação

`agents/qa-devops.md` contém exemplos legados com serviços `moschettieri-*` e `git pull`. Aplicar seus princípios de diagnóstico, build e validação, mas os comandos operacionais devem refletir o fluxo Telz imutável existente em S8. Não executar exemplos legados por analogia. `docs/UPDATE_TELZ_VPS.md` também contém targets/cadeias datados: conferir cada valor contra scripts/manifests do SHA aprovado antes da janela.

1. Confirmar autorização da release, SHA completo e CI correspondente, feature flags inicialmente desligadas, serviços/caminhos efetivos e release ativa (`/var/lib/telz/current`). Inspecionar logs e revision real sem expor segredos; não alterar checkout sujo.
2. Comprovar backup legível e restore ensaiado em clone descartável. Ensaiar migrations e compatibilidade de código anterior com schema expandido; definir critérios de abortar/recuperar por release.
3. Usar o caminho aprovado de S8: helper root-owned `telz-deploy-from-origin` com SHA completo, workflow remoto ou pacote selado verificado. O helper executa build isolado, backup, migration e promoção; não chamar `git pull`, instalador ou Alembic isoladamente na produção.
4. Verificar target/revision/manifests/hashes e os pares de rollback suportados. Schema expansivo não garante, sozinho, rollback seguro. Não presumir transitividade entre pares listados.
5. Validar build e promoção, health local/HTTPS, logs correlacionados e fluxo autenticado cliente/admin por tenant. Testar entrega separadamente de retirada/salão e imprimir etiqueta piloto. `/health`, serviço ativo e HTTP 401 sem autenticação não comprovam operação de receitas/estoque.
6. Ativar piloto por escopo explícito, monitorar falhas/idempotência, filas, latência, saldo negativo, divergências e perda; reconciliar abertura/fechamento antes de ampliar.
7. Em falha, interromper ampliação e diagnosticar logs; desativar nova feature não desfaz movimentos reais. Recuperar código apenas quando schema/contratos forem compatíveis; preservar auditoria e rastreabilidade, preferir correção forward. Restore coordenado de banco + release somente por plano explícito com avaliação de operações posteriores. Não apagar movimentos, adulterar `alembic_version` ou fazer downgrade destrutivo para esconder divergência.

## 9. Gate de saída da Fase 0 e bloqueios posteriores

### Aceite documental F0

- Cinco módulos presentes, requisitos numerados e ligados a fontes reais, evolução proposta, fase e teste/gate.
- Fontes atuais separadas de propostas e de documentação antiga; limites de auditoria estática explícitos.
- Política proposta de legado, tenant, consumo/versão/tentativa, precisão e integridade encaminhada ao Arquiteto sem declaração de implantação.
- Decisões D1–D5 com alternativa, recomendação e ponto de bloqueio; nenhuma registrada como aprovada sem manifestação do gestor.
- Estratégia de banco descartável, concorrência, ausência de skips críticos, regressão, deploy e recuperação documentada.
- Revisão cruzada do Orquestrador confirma alinhamento com o documento arquitetural e ausência de mudança de código/banco fora dos documentos autorizados.

Cumpridos esses itens, **o pacote documental da F0 pode ser entregue para revisão**. Isso não declara as funcionalidades aprovadas em G2/G3/G4, não aprova D1–D5 e não autoriza implementar automaticamente. Registrar revisão/aceite do gestor como evento separado quando houver.

### Bloqueios para fases futuras

Implementação requer autorização expressa da fase e estrutura/contratos definidos; mudança persistida exige migration revisada. Ativação requer decisões pertinentes confirmadas, testes críticos sem skip, ensaio de schema/restore, fluxos integrados e piloto proporcionais ao risco. Infraestrutura indisponível impede comprovação runtime, mas não invalida o aceite documental da F0. Nenhuma decisão ou evidência runtime foi obtida por decurso de prazo.

### Registro da validação desta entrega

Executado: leitura estática dos papéis PO/QA, fontes/testes/workflows citados e revisão textual do documento. Não executado: pytest/Vitest, typecheck/build, navegador, consulta ao banco, migrations, CI remoto, VPS, impressão física. A validação documental final e conferência de diff pertencem à consolidação do Orquestrador.
