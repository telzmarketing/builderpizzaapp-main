# Gestao ERP - Fase 10 Operacao, Validacao e Rollback

Status: concluido como camada operacional/documental
Data: 2026-07-01

## 1. Objetivo

Fechar o ciclo de implantacao dos modulos de Gestao ERP sem criar fluxo paralelo ao sistema atual.

Esta fase consolida:

- Validacao ponta a ponta.
- Ordem segura de ativacao dos modulos.
- Criterios de pronto para producao.
- Plano de rollback por fase.
- Limites operacionais para evitar impacto em checkout, cozinha, pedidos, pagamentos, CRM, marketing e logistica.

## 2. Modulos cobertos

### Estoque

Arquivos principais:

- `backend/models/inventory.py`
- `backend/schemas/inventory.py`
- `backend/services/inventory_service.py`
- `backend/routes/inventory.py`
- `client/pages/admin/gestao/GestaoInventory.tsx`

Uso operacional:

- Manter `inventory.enabled=false` ate finalizar cadastros, compras, entradas e fichas tecnicas.
- Ativar `inventory.sales_control_enabled=true` somente quando todos os itens vendidos possuirem ficha tecnica ou produto acabado configurado.
- Com controle de venda ativo, item sem saldo de insumo obrigatorio deve ficar indisponivel para o cliente.
- A cozinha nao deve ser bloqueada por Estoque.

### CMV

Arquivos principais:

- `backend/models/cmv.py`
- `backend/services/cmv_service.py`
- `backend/services/cmv_snapshot_service.py`
- `backend/routes/cmv.py`
- `client/pages/admin/gestao/GestaoCmv.tsx`

Uso operacional:

- Manter `cmv.enabled=false` ate existir ficha tecnica confiavel.
- CMV nao altera cozinha, pedido, estoque ou StateMachine.
- DRE deve aparecer parcial sem CMV e completa somente com snapshots confiaveis.

### Financeiro

Arquivos principais:

- `backend/models/finance.py`
- `backend/services/finance_service.py`
- `backend/routes/finance.py`
- `client/pages/admin/gestao/GestaoFinance.tsx`

Uso operacional:

- Manter automacoes desligadas ate validar contas e categorias.
- `finance.auto_create_receivables=true` cria recebiveis idempotentes por pagamento confirmado.
- `finance.auto_create_payables_from_purchases=true` cria contas a pagar por compra de estoque confirmada.
- Estornos geram reversao financeira por evento `PaymentReversed`.
- Lancamentos usam centro de custo para relatorios gerenciais.

### Fiscal SEFAZ

Arquivos principais:

- `backend/models/fiscal.py`
- `backend/schemas/fiscal.py`
- `backend/services/fiscal_service.py`
- `backend/routes/fiscal.py`
- `client/pages/admin/gestao/GestaoFiscal.tsx`

Uso operacional:

- O fiscal e interno/autossuficiente.
- Nao usar Saipos, Bling, Tiny, PlugNotas, TecnoSpeed ou middleware fiscal externo.
- Antes de transmitir, configurar empresa fiscal, serie, certificado e perfis tributarios.
- O sistema nao deve simular autorizacao fiscal. Documento so pode ser considerado autorizado apos retorno SEFAZ real.

## 3. Ordem segura de ativacao

1. Habilitar Gestao apenas para configuracao.
2. Cadastrar insumos, unidades, locais e fornecedores.
3. Cadastrar fichas tecnicas internas do catalogo.
4. Validar disponibilidade publica com Estoque ainda em modo controlado.
5. Ativar Estoque operacional.
6. Ativar CMV e validar snapshots por pedido.
7. Configurar contas, categorias, favorecidos e centros de custo.
8. Ativar recebiveis automaticos.
9. Ativar contas a pagar por compras confirmadas.
10. Configurar Fiscal SEFAZ em homologacao.
11. Gerar documento fiscal por pedido em homologacao.
12. Habilitar transmissao SEFAZ direta somente depois de certificado e ambiente validos.

## 4. Validacao ponta a ponta

### Base admin

- Abrir `/painel/gestao/estoque`, `/painel/gestao/cmv`, `/painel/gestao/financeiro` e `/painel/gestao/fiscal`.
- Confirmar que Estoque, CMV, Financeiro e Fiscal carregam pela navegacao administrativa.
- Confirmar que os modulos podem ficar desabilitados sem quebrar pedido, checkout, cozinha ou pagamento.

### Catalogo e ficha tecnica

- Cadastrar insumo.
- Cadastrar ficha tecnica em produto de venda.
- Confirmar que a ficha nao aparece na loja publica.
- Confirmar que produto sem ficha aparece com status interno pendente no CMV.

### Estoque e disponibilidade

- Registrar entrada manual ou compra.
- Validar saldo do insumo.
- Ativar controle de venda.
- Reduzir saldo do insumo obrigatorio ate ficar insuficiente.
- Confirmar que produtos dependentes aparecem indisponiveis no cliente.
- Confirmar que cozinha nao muda comportamento por causa do Estoque.

### Pedido, pagamento e CMV

- Criar pedido com produto que possui ficha tecnica.
- Confirmar pagamento.
- Confirmar que pedido segue fluxo normal.
- Confirmar snapshot de CMV quando CMV estiver habilitado.
- Confirmar DRE parcial sem CMV e completa com CMV operacional confiavel.

### Financeiro

- Ativar `auto_create_receivables`.
- Confirmar pagamento e validar recebivel financeiro.
- Estornar pagamento e validar reversao financeira.
- Confirmar compra de estoque e validar conta a pagar.
- Baixar uma despesa parcial e total.
- Validar caixa, competencia, DRE, canal, categoria e centro de custo.

### Fiscal SEFAZ

- Cadastrar empresa fiscal.
- Cadastrar certificado.
- Cadastrar serie NFC-e/NF-e em homologacao.
- Cadastrar perfil tributario do produto.
- Gerar documento fiscal a partir de pedido.
- Confirmar snapshot de itens e XML interno.
- Assinatura/transmissao devem bloquear se certificado ou integracao SEFAZ direta nao estiverem configurados.
- Consultar evento fiscal e historico.

## 5. Validacoes tecnicas

Executar antes de producao:

```powershell
npm.cmd run typecheck
npm.cmd run build
npm.cmd test
git diff --check
```

Executar em ambiente com Python instalado:

```powershell
py -m py_compile backend\models\inventory.py backend\models\cmv.py backend\models\finance.py backend\models\fiscal.py
py -m py_compile backend\services\inventory_service.py backend\services\cmv_service.py backend\services\finance_service.py backend\services\fiscal_service.py
alembic -c backend\alembic.ini heads
alembic -c backend\alembic.ini upgrade head
```

Observacao: neste host local, `py` pode existir sem runtime Python instalado. Nesse caso, a validacao Python deve ocorrer no VPS/ambiente backend.

## 6. Plano de rollback por fase

### Fase 1 - Base Gestao

Rollback operacional:

- Desabilitar os modulos em Gestao.
- Remover permissoes novas apenas se houver conflito de RBAC.

Rollback tecnico:

- Reverter migration `20260625_gestao_phase1_base` em ambiente controlado.

### Fase 2 - Cadastros de Estoque

Rollback operacional:

- Manter `inventory.enabled=false`.
- Nao excluir cadastros se ja houver relacionamento com ficha tecnica.

Rollback tecnico:

- Reverter migrations de estoque somente se nao houver movimentos reais.

### Fase 3 - Ficha tecnica

Rollback operacional:

- Desativar fichas tecnicas ou manter sem habilitar Estoque/CMV.
- Produtos publicos continuam vendendo sem expor ficha.

Rollback tecnico:

- Reverter tabelas de receitas apenas se nao houver snapshots ou uso por pedidos.

### Fase 4 - Estoque operacional

Rollback operacional:

- Definir `inventory.sales_control_enabled=false`.
- Definir `inventory.auto_consume_on_preparing=false`.
- Manter movimentos para auditoria.

Rollback tecnico:

- Nao apagar movimentos de estoque em producao. Se necessario, criar ajuste inverso.

### Fase 5 - CMV

Rollback operacional:

- Definir `cmv.enabled=false`.
- DRE volta para parcial sem CMV.

Rollback tecnico:

- Preservar snapshots ja criados para auditoria.

### Fase 6/7/8 - Financeiro

Rollback operacional:

- Desativar `finance.auto_create_receivables`.
- Desativar `finance.auto_create_payables_from_purchases`.
- Cancelar lancamentos automaticos indevidos pelo proprio modulo, sem deletar historico.

Rollback tecnico:

- Nao remover `finance_transactions` ou `finance_settlements` se houver baixa real.
- Reversoes devem ser feitas por lancamentos/cancelamentos auditaveis.

### Fase 9 - Fiscal SEFAZ

Rollback operacional:

- Desabilitar `sefaz_integration_enabled`.
- Manter Fiscal em homologacao.
- Nao transmitir documentos novos.

Rollback tecnico:

- Nao apagar documentos fiscais autorizados, rejeitados ou cancelados.
- Preservar XML, protocolos e eventos por obrigacao de auditoria.
- Se um documento foi emitido em homologacao, pode ser mantido como historico tecnico.

## 7. Criterios de pronto para producao

- Build e testes frontend passam.
- Alembic aplica ate `head` em ambiente backend.
- Modulos ficam desabilitados sem side effect.
- Estoque bloqueia venda apenas quando controle operacional esta habilitado.
- CMV nao interfere na cozinha.
- Financeiro e idempotente em pagamento, estorno e compra confirmada.
- Fiscal nao simula autorizacao.
- Rollback operacional esta documentado.

## 8. Decisao final da Fase 10

O ERP de Gestao esta fechado em sua primeira versao modular.

O proximo passo operacional nao e criar nova fase de codigo, mas validar em ambiente com banco real, aplicar migrations, configurar modulos gradualmente e somente entao ativar automacoes em producao.
