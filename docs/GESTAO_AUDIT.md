# Gestao ERP - Auditoria Tecnica Fase 0

Data: 2026-06-25

## 1. Resumo executivo

Esta auditoria prepara a criacao da categoria administrativa **Gestao**, com os modulos Estoque, CMV, Financeiro e Fiscal interno/autossuficiente.

Conclusao principal: o nucleo atual esta forte em pedido, checkout, Mercado Pago, cozinha, logistica, CRM e marketing, mas ainda nao possui as estruturas centrais de ERP: estoque por movimento, ficha tecnica operacional, snapshot de CMV, ledger financeiro completo e fiscal interno. A implementacao deve ser faseada e nao pode alterar a operacao existente enquanto os modulos estiverem desabilitados.

Decisoes de negocio incorporadas nesta auditoria:

- Estoque deve ter opcao de habilitar/desabilitar.
- CMV deve ter opcao de habilitar/desabilitar e nao pode interferir na cozinha.
- CMV deve ser analitico e seguro: nao bloqueia pedido, nao muda status, nao altera fila de preparo.
- Financeiro deve ser completo, mas dividido em fases.
- DRE sem CMV deve aparecer como **parcial**.
- DRE com CMV estimado deve aparecer como **parcial estimada**.
- DRE com CMV habilitado e snapshots confiaveis deve aparecer como **completa**.
- Fiscal deve ser interno/autossuficiente, sem Saipos ou middleware fiscal externo, mas com integracao oficial direta com SEFAZ.
- Quando o Estoque operacional estiver habilitado, item do catalogo afetado por falta de insumo/produto em estoque nao deve ser vendido; a loja deve mostrar **indisponivel no momento**.

## 2. Escopo da auditoria

Arquivos e areas inspecionados:

- `KNOWLEDGE_BASE.md`
- `package.json`
- `client/App.tsx`
- `client/config/adminNavigation.ts`
- `client/config/adminPageMeta.ts`
- `client/components/layout/AdminLayout.tsx`
- `client/components/AdminGuard.tsx`
- `client/lib/api.ts`
- `client/lib/adminAccess.ts`
- `backend/main.py`
- `backend/core/events.py`
- `backend/core/state_machine.py`
- `backend/core/seed.py`
- `backend/models/order.py`
- `backend/models/payment.py`
- `backend/models/product.py`
- `backend/models/rbac.py`
- `backend/routes/orders.py`
- `backend/routes/payments.py`
- `backend/routes/rbac.py`
- `backend/services/order_service.py`
- `backend/services/payment_service.py`
- `backend/migrations/versions/*`

Esta fase nao implementa funcionalidade. O unico artefato gerado e este documento.

## 3. Mapa de arquitetura atual

### Frontend administrativo

- Rotas administrativas ficam em `client/App.tsx`.
- O shell administrativo usa `AdminGuard` e `AdminLayout`.
- As rotas protegidas ficam abaixo de `AdminGuard`.
- A maior parte das paginas admin fica abaixo de `AdminLayout`.
- A navegacao lateral/topo e centralizada em `client/config/adminNavigation.ts`.
- Metadados de pagina ficam em `client/config/adminPageMeta.ts`.
- Controle de acesso visual usa `client/lib/adminAccess.ts` e as permissoes carregadas pelo `AdminGuard`.
- Chamadas de API devem passar por `client/lib/api.ts`.

Padrao recomendado para Gestao:

- Criar grupo unico `Gestao` em `adminNavigation.ts`.
- Criar rotas:
  - `/painel/gestao/estoque`
  - `/painel/gestao/cmv`
  - `/painel/gestao/financeiro`
  - `/painel/gestao/fiscal`
- Criar metadados correspondentes em `adminPageMeta.ts`.
- Criar lazy imports em `client/App.tsx`.
- Usar paginas dentro de `AdminLayout`, sem shell proprio.
- Usar tabs internas apenas dentro de cada modulo, seguindo exemplos como `client/pages/admin/logistica/AdminLogistica.tsx` e `client/pages/admin/crm/CrmAgenteWhatsApp.tsx`.

### Backend

- `backend/main.py` registra routers com e sem prefixo `/api`.
- `backend/main.py` tambem roda `create_all_tables()`, `_run_migrations()` e `seed_all(db)` no startup.
- Regras de negocio estao em services, principalmente `OrderService` e `PaymentService`.
- Rotas de pedidos e pagamentos delegam para services.
- Eventos de dominio ficam em `backend/core/events.py`.
- StateMachine central fica em `backend/core/state_machine.py`.
- Migrations Alembic ficam em `backend/migrations/versions`.

Ponto de atencao: `_run_migrations()` em `backend/main.py` possui muitos fallbacks idempotentes de schema. As novas tabelas de Gestao devem usar Alembic e nao depender de fallback silencioso de startup.

## 4. Modelo atual relevante

### Produtos, tamanhos e variantes

Modelo principal: `backend/models/product.py`.

Persistencia atual:

- `products`: produto base, preco, categoria, subcategoria, tipo, visibilidade delivery/salao, ativo.
- `product_sizes`: tamanhos por produto, com preco proprio.
- `product_crust_types`: bordas/tipos de borda por produto, com acrescimo de preco.
- `product_drink_variants`: variantes de bebida por produto.
- `multi_flavors_config`: configuracao global de multi-sabores, com maximo de sabores, regra de preco e filtros de categoria.

Ponto importante para Estoque/CMV:

- Ficha tecnica nao deve criar cadastro concorrente de produto, tamanho, borda ou sabor.
- Ficha tecnica deve referenciar os IDs reais ja existentes quando houver relacao com produto/tamanho/borda/variante.
- Pizza multi-sabor deve usar os sabores persistidos em `order_item_flavors`.

### Pedidos e composicao dos itens

Modelo principal: `backend/models/order.py`.

Persistencia atual:

- `orders`: status, cliente, endereco inline, canal, mesa/sessao, valores, desconto, frete, timestamps operacionais.
- `order_items`: produto, tamanho selecionado, `selected_size_id`, divisao de sabores, quantidade de sabores, borda selecionada, variante de bebida, precos e campos promocionais.
- `order_item_flavors`: sabores escolhidos por item, com `product_id`, nome, preco e posicao.

Observacao critica sobre adicionais:

- O schema aceita `add_ons`.
- O frontend envia `add_ons`.
- Nao foi encontrada coluna equivalente em `OrderItem` nem consolidacao clara no service.
- Antes de usar adicionais em CMV, e preciso formalizar persistencia/preco/historico ou declarar que nao participam da primeira versao do CMV.

### Status do pedido e cozinha

StateMachine atual permite:

- `pending` / `waiting_payment` / `aguardando_pagamento` para `paid`, `pago`, `preparing` e cancelamentos.
- `paid` / `pago` para `preparing`, `cancelled`, `refunded`.
- `preparing` para `ready_for_pickup`, `on_the_way`, `cancelled`.

Ponto real em que pedido entra em preparo:

- `PUT /orders/{order_id}/status` chama `OrderService.change_status`.
- Ao mudar para `preparing`, `preparation_started_at` e preenchido.
- Existe fluxo de salao que pode criar pedido diretamente como `preparing`.

Decisao para CMV e Estoque:

- Nao mudar a StateMachine.
- Nao bloquear cozinha.
- Usar `OrderStatusChanged(to_status="preparing")` como sinal de leitura para Estoque/CMV apenas quando os modulos estiverem habilitados.
- CMV deve ser analitico e nao deve disparar movimento de estoque por conta propria.

### Pagamentos

Modelo principal: `backend/models/payment.py`.

Fluxo atual:

- Mercado Pago e o gateway ativo do checkout.
- Frontend nao marca pedido como pago.
- Webhook consulta a API do Mercado Pago antes de aplicar status.
- `PaymentStatus.approved` mapeia pedido para `OrderStatus.paid`.
- `PaymentService._apply_status` publica `PaymentConfirmed` quando o status muda para aprovado.
- Pagamento manual e dinheiro/admin tambem passam pelo service.

Lacuna de estorno:

- Existe `PaymentStatus.refunded`.
- StateMachine permite alguns caminhos para `refunded`.
- O webhook mapeia `refunded`, mas nao ha evento especifico `PaymentRefunded`.
- `_order_status_for_payment` nao mapeia refund para pedido.
- Financeiro completo precisara tratar estorno/reversao com idempotencia propria.

### Eventos

Eventos atuais relevantes:

- `OrderCreated`
- `OrderStatusChanged`
- `OrderCancelled`
- `PaymentCreated`
- `PaymentConfirmed`
- `PaymentFailed`
- eventos de delivery e loyalty

O event bus atual e sincrono e loga falhas de handlers. Para a primeira versao da Gestao, os handlers devem ser idempotentes e nao podem quebrar checkout/cozinha. Para automacoes criticas futuras, considerar outbox persistente.

### RBAC

Modelos:

- `rbac_modules`
- `rbac_permissions`
- `role_permissions`
- `user_permissions`

Permissoes base atuais:

- `view`
- `create`
- `edit`
- `delete`
- `approve`
- `export`
- `manage`

Modulos existentes incluem `financeiro` e `fluxo_caixa`, mas nao existem ainda `inventory`, `cmv` ou `fiscal`.

Decisao:

- Reutilizar o RBAC existente.
- Adicionar modulos RBAC novos por migration/seed idempotente.
- Nao criar segundo sistema de autorizacao.

## 5. Configuracoes obrigatorias por modulo

### Estoque

Configuracoes iniciais:

- `inventory.enabled`: padrao `false`.
- `inventory.auto_consume_on_preparing`: padrao `false`.
- `inventory.negative_stock_policy`: padrao `warn_only`.
- `inventory.sales_control_enabled`: padrao `false`.
- `inventory.out_of_stock_behavior`: padrao `show_unavailable`.
- `inventory.alerts_enabled`: padrao `false` enquanto `inventory.enabled=false`.

Regras:

- Se `inventory.enabled=false`, nao gerar consumo, reversao, alerta automatico ou movimento por pedido.
- A empresa pode cadastrar insumos e fichas antes de ativar.
- Habilitar Estoque nao deve bloquear cozinha.
- Baixa automatica so pode existir se `inventory.enabled=true` e `auto_consume_on_preparing=true`.
- Se `inventory.enabled=true` e `inventory.sales_control_enabled=true`, a loja deve validar disponibilidade antes de permitir venda.
- Item do catalogo sem saldo suficiente de produto acabado ou de qualquer insumo obrigatorio da ficha tecnica deve aparecer como **indisponivel no momento** e nao pode ser adicionado/finalizado no checkout.
- A validacao de disponibilidade deve considerar a quantidade necessaria por item, tamanho, sabor, complemento e ficha tecnica vigente.
- `inventory.negative_stock_policy=warn_only` vale para movimentos internos e fase preparatoria; controle de venda usa `sales_control_enabled`.

### CMV

Configuracoes iniciais:

- `cmv.enabled`: padrao `false`.
- `cmv.mode`: `disabled`, `estimated` ou `snapshot_from_inventory`.
- `cmv.target_percent`: opcional.
- `cmv.estimated_mode_allowed`: padrao `true`.

Regras:

- Se `cmv.enabled=false`, nao gerar snapshot automatico nem alerta operacional.
- CMV nao altera pedido.
- CMV nao altera cozinha.
- CMV nao altera estoque.
- CMV nao muda StateMachine.
- CMV nao bloqueia pedido por custo; bloqueio de venda por falta de saldo e responsabilidade do Estoque ativo.
- CMV pode gerar relatorio estimado quando configurado.
- Historico automatico so comeca a partir da habilitacao.

### Financeiro

Configuracoes iniciais:

- `finance.enabled`: padrao a definir na fase de implementacao.
- `finance.auto_create_receivables`: padrao seguro `false` ate confirmacao operacional.
- `finance.auto_create_payables_from_purchases`: depende de Compras/Estoque.
- `finance.cash_basis_enabled`: `true`.
- `finance.accrual_basis_enabled`: `true`.
- `finance.dre_enabled`: `true`.

Regra de DRE:

- Sem CMV: DRE **parcial**.
- CMV estimado: DRE **parcial estimada**.
- CMV com snapshots confiaveis: DRE **completa**.

### Fiscal

Configuracoes iniciais:

- Fiscal interno/autossuficiente.
- Sem Saipos, Bling, Tiny, PlugNotas, TecnoSpeed ou middleware fiscal equivalente.
- Com integracao oficial direta com SEFAZ.
- Certificado digital, assinatura, envio, consulta, cancelamento, inutilizacao e armazenamento fiscal devem ficar sob responsabilidade do ERP.
- Sem emissao pelo frontend.
- Emissao fiscal oficial depende de autorizacao SEFAZ.

## 6. Lacunas encontradas

- Nao ha tabela de estoque, insumos, compras, movimentos ou saldos.
- Nao ha ficha tecnica operacional.
- Nao ha snapshot de CMV.
- Nao ha ledger financeiro completo.
- Nao ha contas a pagar/receber estruturadas.
- Nao ha conciliacao financeira.
- Nao ha documento fiscal interno.
- Nao ha evento especifico para estorno financeiro/fiscal.
- `add_ons` nao parecem persistidos de forma utilizavel para CMV.
- `store_id`/`tenant_id` nao existem no core de pedidos/produtos/pagamentos.
- O event bus e sincrono, sem outbox persistente.
- Algumas migrations/fallbacks rodam no startup com risco de erro silencioso.

## 7. Decisoes propostas

1. Tratar a Gestao como camada incremental sobre fatos operacionais existentes.
2. Nao alterar checkout, Mercado Pago, pedidos, cozinha, logistica, CRM, Marketing ou BI nas fases iniciais.
3. Criar configuracoes de modulo antes de qualquer automacao.
4. Estoque deve nascer desabilitado e preparatorio.
5. CMV deve nascer desabilitado e analitico, sem interferir na cozinha.
6. Usar `OrderStatusChanged(to_status="preparing")` como ponto de leitura para consumo/snapshot somente se os modulos estiverem habilitados.
7. Usar `PaymentConfirmed` para Financeiro, de forma idempotente, sem substituir `PaymentService`.
8. Criar evento/rotina especifica para estorno antes de automatizar reversoes financeiras.
9. Fiscal deve ser interno/autossuficiente, sem middleware fiscal externo, mas integrado oficialmente a SEFAZ.
10. Para a primeira versao, assumir escopo single-store/default, sem adicionar `store_id` no core por suposicao. Se multiempresa virar requisito, abrir fase propria de tenancy.
11. Formalizar adicionais antes de inclui-los no CMV; ate la, marcar como limitacao.
12. Quando o controle operacional de Estoque estiver ativo, qualquer item do catalogo afetado por falta de produto acabado ou insumo obrigatorio deve ficar indisponivel para venda na loja.
13. Toda tabela nova deve ter migration Alembic reversivel quando tecnicamente possivel.

## 8. Plano de migrations

### Fase 1 - Base Gestao

- Adicionar modulos RBAC:
  - `inventory`
  - `cmv`
  - `finance`
  - `fiscal`
- Avaliar se `financeiro` e `fluxo_caixa` existentes serao preservados como aliases/permissoes antigas ou migrados para `finance`.
- Criar tabela ou configuracao persistida para flags de Gestao, preferencialmente por dominio:
  - `inventory_settings`
  - `cmv_settings`
  - `financial_settings`
  - `fiscal_settings`

### Estoque

Tabelas sugeridas:

- `inventory_categories`
- `inventory_items`
- `inventory_unit_conversions`
- `inventory_locations`
- `inventory_balances`
- `inventory_movements`
- `suppliers`
- `purchase_entries`
- `purchase_entry_items`
- `recipes`
- `recipe_components`
- `inventory_counts`
- `inventory_count_items`

Constraints obrigatorias:

- chave unica para idempotencia em movimentos.
- saldo unico por item/local.
- FKs para produto/tamanho/borda quando houver vinculo real.
- `NUMERIC(18,6)` para quantidade.
- `NUMERIC(18,4)` ou equivalente para custo/valor monetario.

### CMV

Tabelas sugeridas:

- `order_cost_snapshots`
- `order_cost_snapshot_items`
- `cmv_targets`
- `cmv_alerts` se persistencia de alertas for justificada.

Constraints obrigatorias:

- snapshot unico por pedido/item/versao.
- idempotencia por chave de calculo.
- valores historicos imutaveis.

### Financeiro

Subdividir migrations conforme fases:

- Cadastros: contas, categorias, centros de custo, favorecidos.
- Lancamentos: entradas financeiras, status, vencimento, competencia.
- Liquidacoes: settlements, parcial/total, tarifas, juros, multa, desconto.
- Transferencias.
- Conciliacao.
- Auditoria financeira.
- Chaves de idempotencia para eventos automaticos.

### Fiscal interno

Tabelas sugeridas:

- `fiscal_settings`
- `fiscal_product_tax_profiles`
- `fiscal_documents`
- `fiscal_document_items`
- `fiscal_document_events`

Estados internos sugeridos:

- `draft`
- `queued`
- `processing`
- `authorized_internal`
- `rejected_internal`
- `cancel_pending`
- `cancelled`
- `error`

## 9. Plano de implementacao por fases

### Fase 0 - Auditoria e desenho executivo

- Mapear frontend, backend, banco, eventos, RBAC, migrations e fluxos atuais.
- Confirmar que Saipos e middleware fiscal externo ficam fora da arquitetura.
- Definir Estoque e CMV como modulos opcionais, com `enabled=false` por padrao.
- Definir Financeiro completo em fases.
- Definir Fiscal real com integracao direta SEFAZ.
- Entrega: `docs/GESTAO_AUDIT.md`.

### Fase 1 - Base da categoria Gestao

- Criar categoria administrativa **Gestao**.
- Criar navegacao, page meta e rotas protegidas.
- Criar permissoes/RBAC para `inventory`, `cmv`, `finance` e `fiscal`.
- Criar APIs de configuracao dos modulos.
- Criar paginas placeholder seguras com estados de habilitado/desabilitado.
- Nenhuma automacao operacional nesta fase.

### Fase 2 - Cadastros base de Estoque

- Cadastrar insumos, produtos de estoque, unidades, categorias, locais e fornecedores.
- Cadastrar compras em rascunho e entradas manuais.
- Manter `inventory.enabled=false` por padrao.
- Nao alterar pedidos, checkout, cozinha ou catalogo publico.
- Entrega: base pronta para receber ficha tecnica.

### Fase 3 - Ficha tecnica interna do Catalogo

- Adicionar aba interna de ficha tecnica no cadastro de produtos de venda.
- Relacionar produto/tamanho/sabor/complemento aos insumos usados.
- Informar quantidade consumida por insumo, unidade de medida, perda tecnica opcional e versao vigente.
- Ocultar totalmente essa informacao do cliente final.
- Versionar ou criar snapshot para que pedidos antigos nao sejam recalculados com ficha nova.

### Fase 4 - Estoque operacional e disponibilidade de venda

- Ativar movimentos, saldos, inventario, perdas, ajustes e custo medio ponderado.
- Separar politica interna `warn_only` da politica de venda publica.
- Controlar venda apenas com `inventory.enabled=true` e `inventory.sales_control_enabled=true`.
- Se faltar mussarela, por exemplo, todas as pizzas/itens cuja ficha tecnica use mussarela ficam **indisponivel no momento**.
- Bloquear adicao/finalizacao no checkout de item afetado por falta de produto acabado ou insumo obrigatorio.
- Nao bloquear cozinha nem alterar status de pedido existente.

### Fase 5 - CMV analitico e seguro

- Manter `cmv.enabled=false` por padrao.
- Criar snapshots de custo somente quando habilitado.
- Calcular CMV por pedido/item usando ficha tecnica, custo medio e snapshot vigente.
- Nao alterar cozinha, pedido, estoque ou StateMachine.
- DRE sem CMV fica **parcial**; com CMV estimado fica **parcial estimada**; com CMV confiavel fica **completa**.

### Fase 6 - Financeiro base completo

- Criar contas financeiras, categorias hierarquicas, centros de custo e favorecidos.
- Criar contas a pagar, contas a receber e lancamentos manuais.
- Suportar anexos, observacoes, auditoria e permissao por acao.
- Ainda sem substituir `PaymentService`.

### Fase 7 - Financeiro operacional

- Liquidacao parcial/total.
- Juros, multa, desconto, tarifas e baixas.
- Parcelamentos, recorrencias e transferencias entre contas.
- Conciliacao manual.
- Fluxo de caixa realizado e previsto.

### Fase 8 - Financeiro integrado e gerencial

- Criar recebiveis de forma idempotente a partir de pagamento aprovado.
- Criar reversoes por estorno/cancelamento depois de contrato/evento confiavel.
- Gerar contas a pagar por compra confirmada.
- Separar receita de produto, frete, taxas de gateway e descontos.
- Entregar dashboard financeiro, caixa/competencia, DRE e relatorios por canal, categoria e centro de custo.

### Fase 9 - Fiscal SEFAZ nativo

- Criar cadastro fiscal da empresa, regime tributario, series, numeracao e certificado digital.
- Criar perfis tributarios por produto: NCM, CEST, CFOP, CST/CSOSN e aliquotas aplicaveis.
- Gerar XML com itens em snapshot fiscal.
- Assinar, transmitir, consultar, cancelar e inutilizar documentos fiscais via SEFAZ.
- Armazenar XML, protocolo, rejeicoes, autorizacoes e historico.
- Nao usar Saipos, Bling, Tiny, PlugNotas, TecnoSpeed ou middleware fiscal externo.

### Fase 10 - Integracao final, testes e operacao

- Testar fluxo ponta a ponta: catalogo, ficha tecnica, estoque, disponibilidade, checkout, pedido, pagamento, CMV, financeiro e fiscal.
- Criar documentacao operacional.
- Atualizar `KNOWLEDGE_BASE.md`.
- Criar plano de rollback por fase.
- Entregar validacao completa antes de ativar modulos em producao.

## 10. O que nao sera alterado

Nao alterar nesta trilha sem decisao explicita:

- Checkout publico.
- Mercado Pago e Payment Brick.
- Contratos publicos de pedidos.
- Contratos publicos de pagamentos.
- StateMachine de pedidos/pagamentos.
- Fila da cozinha.
- Logistica/motoboys.
- CRM.
- Marketing.
- BI.
- Configuracoes de loja online.
- Fluxo de WhatsApp/Agente WhatsApp.
- Sistema de upload.
- Stack do projeto.
- Autorizacao/RBAC existente como arquitetura; apenas estender modulos/permissoes.

## 11. Riscos

### Alto

- CMV acoplado a cozinha pode travar operacao. Mitigacao: CMV analitico, sem side effect.
- Estoque automatico antes de cadastro completo pode gerar saldos errados. Mitigacao: `inventory.enabled=false` e `auto_consume_on_preparing=false`.
- Financeiro pode duplicar pagamentos se tentar substituir `PaymentService`. Mitigacao: consumir eventos e usar idempotencia.
- Estorno ainda nao tem evento completo. Mitigacao: criar evento/contrato antes de automatizar reversoes.

### Medio

- Adicionais nao persistidos podem distorcer CMV. Mitigacao: excluir da primeira versao ou formalizar persistencia.
- Tenancy nao e transversal. Mitigacao: primeira versao single-store/default; multiempresa vira fase propria.
- `_run_migrations()` silencioso pode mascarar erro. Mitigacao: validar Alembic explicitamente.
- Event bus sincrono nao garante retry. Mitigacao: handlers idempotentes agora; outbox em fase futura se necessario.

## 12. Validacao recomendada para proximas fases

Frontend:

- `npm.cmd run typecheck`
- `npm.cmd run build`
- `npm.cmd test`

Backend:

- `alembic -c backend/alembic.ini heads`
- `alembic -c backend/alembic.ini upgrade head`
- teste de downgrade quando suportado.
- testes Python em ambiente com Python instalado.

Regressao:

- Criar pedido.
- Pagar com Mercado Pago/mock/manual conforme ambiente.
- Atualizar pedido para `preparing`.
- Ver cozinha sem alteracao de comportamento quando Estoque/CMV desabilitados.
- Com Estoque operacional ativo, confirmar que item afetado por falta de produto acabado ou insumo obrigatorio fica **indisponivel no momento** e nao finaliza checkout.
- Confirmar que DRE aparece parcial quando CMV nao estiver habilitado.

## 13. Criterios de aceite da Fase 0

- Documento `docs/GESTAO_AUDIT.md` criado.
- Auditoria cobre frontend, backend, banco, eventos, RBAC e migrations.
- Plano inclui Estoque/CMV opcionais.
- Plano inclui CMV sem interferencia na cozinha.
- Plano inclui bloqueio de venda por indisponibilidade quando Estoque operacional estiver ativo.
- Plano subdivide Financeiro completo.
- Plano define DRE parcial/completa conforme CMV.
- Plano preserva Fiscal interno/autossuficiente com integracao direta SEFAZ e sem middleware fiscal externo.
- Nenhuma funcionalidade operacional nova foi implementada nesta fase.

## 14. Status final da trilha Gestao ERP

Atualizado em: 2026-07-01.

A trilha de implementacao por fases foi executada ate a Fase 10.

Entregas consolidadas:

- Fase 1: categoria administrativa Gestao, navegacao, rotas, RBAC e configuracoes persistidas.
- Fase 2: cadastros base de Estoque.
- Fase 3: ficha tecnica interna do catalogo.
- Fase 4: Estoque operacional e disponibilidade de venda controlada por saldo.
- Fase 5: CMV analitico, snapshots e DRE parcial/completa conforme confiabilidade.
- Fase 6: Financeiro base completo.
- Fase 7: Financeiro operacional com baixas, ajustes e fluxo de caixa.
- Fase 8: Financeiro integrado e gerencial com recebiveis, estornos, compras confirmadas, caixa, competencia, DRE e relatorios por dimensao.
- Fase 9: Fiscal SEFAZ nativo com empresa fiscal, certificado, series, perfis tributarios, documentos, XML interno e eventos.
- Fase 10: documentacao operacional, validacao final e rollback por fase em `docs/gestao-operacao-fase-10.md`.

Decisoes finais:

- Estoque e CMV continuam opcionais por configuracao.
- CMV nao interfere em cozinha, pedido, estoque ou StateMachine.
- Financeiro consome eventos e usa idempotencia; nao substitui `PaymentService`.
- Fiscal e interno/autossuficiente, sem Saipos ou middleware externo.
- Transmissao SEFAZ real depende de certificado, ambiente e integracao direta habilitados; o sistema nao simula autorizacao fiscal.

Validacao tecnica minima desta fase:

- `npm.cmd run typecheck`
- `npm.cmd run build`
- `npm.cmd test`
- `git diff --check`

Validacao Python/Alembic deve ocorrer em ambiente backend com Python instalado.
