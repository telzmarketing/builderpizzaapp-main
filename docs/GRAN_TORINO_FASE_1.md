# Gran Torino — Fase 1: fundação de estoque

Data: 21/10/2026. Classificação: implementação incremental autorizada pelo usuário.

## 1. Entrega e limites

Implementação local da fundação aprovada na [Fase 0](GRAN_TORINO_FASE_0.md), preservando catálogo, usuários, RBAC e o ledger existente. A autorização desta fase não aprova regras sanitárias, custos contábeis novos, corte de produção ou deploy.

O momento do consumo continua `preparing`. A integração com lotes/reservas protege os escritores existentes; não implementa tarefas por unidade/tentativa ou multioperador da fase 7. Ordenação mínima por validade elegível é uma dependência de integridade dos novos lotes, sem antecipar abertura, sublotes, políticas sanitárias, genealogia de preparo ou etiquetas da fase 4.

## 2. Banco e migração

Nova revision: `20261021_inventory_foundation`, filha de `20261020_inventory_recipe_fractions`. A cadeia tem um único head.

- Inventário, compras, entradas, movimentos e receitas passam a `Numeric`: quantidades (20,6), custos/valores de compra (20,8), referência de fração e percentuais (20,12).
- Classificação explícita de unidades: código, dimensão, fator (24,12) e versão. Unidades antigas permanecem sem classificação; símbolo não determina fator automaticamente.
- Novas entidades: `inventory_operations`, `inventory_item_packagings`, `inventory_lots`, `inventory_reservations`.
- Movimentos existentes recebem operação, sequência física, linha lógica e lote opcionais. Saldo continua sendo a soma do mesmo ledger.
- Operação e reserva têm identidades permanentes e constraints de unicidade. Uma linha lógica pode produzir várias sequências físicas em lotes distintos.
- Novas entidades têm tenant obrigatório e relacionamentos compostos tenant-safe. Referências de movimento a item/local também são verificadas para novas escritas. Essas duas FKs usam `NOT VALID` na migration para não reatribuir nem invalidar silenciosamente exceções históricas; validar o legado exige reconciliação separada.
- O preflight verifica finitude, amplitude e escala ANTES de qualquer mutação. Valor incompatível interrompe a migration inteira; não arredonda histórico automaticamente.
- Sem lote, validade, abertura, ownership ou estoque inicial fictícios. Não há downgrade destrutivo.

Financeiro, fiscal e modelos históricos de CMV ainda possuem campos Float: sua migração global não integra esta entrega de inventário. A política gerencial de custo existente não foi substituída por outra política contábil.

## 3. Backend e contratos

Novos arquivos:

- `backend/models/inventory_foundation.py`
- `backend/schemas/inventory_foundation.py`
- `backend/services/inventory_foundation_service.py`
- `backend/routes/inventory_foundation.py`

API canônica: `/api/gestao/inventory/v1`. Entradas novas são Pydantic estritas, rejeitam campos desconhecidos e exigem decimais em strings sem expoente. Saídas usam DTOs explícitos e strings decimais. Contratos antigos continuam retornando números JSON.

| Recurso | Operações |
|---|---|
| Unidades | Listar, criar e classificar unidade existente com versão |
| Embalagens | Listar e confirmar fator fixo ou peso variável por insumo |
| Conversões | Simular sem movimentar; peso variável exige total aferido |
| Lotes | Registrar metadados, listar e alterar bloqueio/quarentena com versão |
| Operações | Entrada, saída, transferência, perda e ajustes manuais explícitos |
| Reservas | Listar, reservar e liberar com auditoria; sem reserva automática de checkout |
| Saldos | Físico, utilizável, reservado e disponível por insumo/local/lote |
| Reconciliação | Leitura das divergências, incluindo origem legada sem lote |

Comandos exigem `Idempotency-Key`; criação exige `expected_version=0`, alteração exige versão vigente. Replay equivalente retorna o resultado anterior, conteúdo diferente retorna conflito e chave nova não contorna identidade física já usada. O resultado persistido conserva o snapshot do pedido de comando, incluindo quantidade/unidade originais; esse snapshot interno não amplia o DTO público.

Consultas de cadastros usam cursor; o API client percorre as páginas para não ocultar registros após o limite de página. Nenhuma mutação é repetida automaticamente pelo frontend.

### Regras físicas

- Conversões dimensionais e por embalagem utilizam Decimal e arredondamento explícito na fronteira de seis casas, sem cálculo comercial no React.
- Conversão massa/volume é recusada sem domínio de densidade cadastrado; embalagem não contorna essa restrição.
- Lote sem validade confirmada permanece em quarentena e não é utilizável. Data de validade respeita o dia no fuso da empresa; limite efetivo usa o prazo mais restritivo informado.
- Reserva manual não consome estoque. Reserva sem lote compromete somente o bucket explicitamente sem lote daquele local, não outro lote.
- Transferência em lote na F1 exige lote inteiro sem reservas; transferência parcial com subdivisão pertence à evolução de rastreabilidade.
- Insuficiência em uma linha desfaz a operação inteira. Outras saídas não podem consumir saldo reservado.
- Bloquear lote não apaga saldo nem libera reservas silenciosamente; a divergência fica visível na reconciliação.
- Expiração da reserva é opcional e explícita; disponibilidade ignora reservas cujo prazo informado já passou, sem inventar duração padrão.

## 4. Compatibilidade e escritores antigos

As rotas antigas de inventário agora aplicam o RBAC existente por ação. O acesso técnico da conta cozinha continua restrito à própria estação; não foi concedido acesso geral ao estoque.

Autorização e consulta usam o mesmo `AuthorizedTenantActor`: flags legadas desligadas não podem trocar o tenant selecionado pelo tenant padrão depois de autorizar a ação. Escritas manuais HTTP conservam o usuário autenticado na auditoria dos movimentos e compensações; caminhos internos de pedidos identificam sua origem de sistema.

`InventoryService` usa Decimal na aritmética física, compras e receitas. O motor compartilhado preserva seu adapter Float para consumidores históricos de CMV, mas fornece multiplicador Decimal independente para estoque, inclusive frações de três sabores. Snapshots antigos não são reprecificados nem reinterpretados como meia pizza.

Escritores manuais antigos serializam no mesmo insumo e validam saldo sem lote/reservas. Excluir uma entrada manual passou a gerar compensação rastreável, preservando a origem e impedindo compensação duplicada ou retirada de saldo comprometido. A interface indica a entrada estornada.

O consumo por pedido mantém lock do pedido e dos insumos. Quando há lotes/reservas, delega ao bridge flush-only da mesma transação e grava `foundation_order_sale`, operação e sequências de lote, evitando o unique legado por pedido/insumo. Quando não há novos controles, preserva o caminho legado. Não há segunda baixa em paralelo.

Consulta de catálogo/carrinho considera saldo utilizável e livre. Na produção, reservas do próprio pedido são reconhecidas; apenas a quantidade realmente consumida é abatida da reserva. Cancelamento libera reservas próprias restantes, conserva consumo realizado e registra perda com delta zero. Pedido cancelado/pronto/em rota/concluído não recebe nova reserva operacional. Exclusão física de pedido reconhece as novas origens de movimento.

Unidade-base de insumo movimentado ou com configuração de fundação não pode mudar silenciosamente. Classificação usada por embalagem/movimento fica protegida; locks e releitura de versões impedem operar com metadata obsoleta após espera concorrente.

## 5. Interface

Nova aba **Saldos e conversões** na página existente de Estoque (`GestaoInventory.tsx`), com componente reutilizável `InventoryFoundationPanel.tsx` e chamadas exclusivamente por `client/lib/api.ts`.

Permite consultar saldos/divergências, classificar unidades existentes, conferir conversão, cadastrar embalagem/lote e confirmar movimento/reserva/liberação. Quantidades permanecem strings; o servidor calcula e valida. Há carregamento, erro, estado vazio e feedback de confirmação. O cliente conserva a chave de comandos ainda sem confirmação por intenção, mesmo se o operador alternar formulários, e bloqueia cliques concorrentes.

Não houve validação visual em navegador real nem homologação por operador nesta etapa; TypeScript, build e contratos HTTP são evidências separadas desse piloto.

## 6. Testes e CI

Suítes novas: `tests/test_inventory_foundation.py`, `tests/test_inventory_foundation_models.py`, `tests/test_inventory_foundation_postgresql.py`.

Cobrem precisão, unidades desconhecidas, embalagem variável, rejeição massa/volume, metadados/tenant forjados, constraints, movimentos entre lotes, idempotência, falha transacional, concorrência reserva/saída, saldo reservado, cancelamento, estorno manual e DTOs HTTP. A suíte antiga de concorrência recebeu as novas tabelas na fixture isolada; sua regra de negócio permaneceu preservada.

CI passou a configurar bancos distintos para runtime, produtos e fundação; o gate JUnit recusa falta de coleta, falha ou skip nas suítes críticas de PostgreSQL. Os workflows e scripts apontam para o novo head. Não foi adicionada compatibilidade de rollback do código antigo com o novo schema.

Os comandos locais usam apenas URLs sintéticas para PostgreSQL descartável. Nunca usam a URL configurada da aplicação como fallback de teste. Resultados consolidados estão na seção 8.

## 7. Implantação, recuperação e pendências

Nenhum commit, push, CI remoto, migration produtiva, restart ou deploy foi executado.

Antes de produção: reconciliar precisão e ownership em clone autorizado, validar as FKs históricas pendentes, testar backup/restore, aprovar cutover e conferir todos os canais de venda com dados reais do piloto. Banco com Float fora da escala alvo é bloqueado pelo preflight e requer tratamento explícito.

O updater preserva o bloqueio para pares de schema não revisados. Retornar a código antigo pode ignorar reservas/lotes e não é um rollback seguro presumido. Usar o processo imutável e o cutover forward-only já suportado somente após aprovação operacional própria.

Fases seguintes continuam necessárias: fichas/instruções completas (F2), XML/financeiro (F3), abertura/FEFO operacional/etiquetas (F4), PCP (F5), consulta e distribuição KDS (F6/F7), planejamento (F8), OCR (F9) e consolidação de CMV/indicadores (F10).

Decisões do gestor registradas em F0 continuam pendentes nos pontos pertinentes. Não foram inventados prazo sanitário, política de custo ou instante novo de consumo.

## 8. Resultado consolidado da validação local

| Verificação | Resultado |
|---|---|
| Backend completo com URLs explícitas de teste | **848 passed, 30 skipped, zero falhas/erros** |
| Rodada focada de fundação, produto, ORM, RBAC e KDS | **99 passed, zero skips**; o caso HTTP legado adicional também passou na suíte completa |
| Gate JUnit de coleta/execução PostgreSQL | **PASS**, inclusive sobre o relatório completo; nenhuma suíte crítica ignorada |
| Frontend Vitest | **130 testes, 27 arquivos, PASS** |
| TypeScript | `npm run typecheck`: **PASS** |
| Build cliente, service worker, servidor e pós-build | `npm run build`: **PASS** |
| YAML e scripts shell dos workflows alterados | Parse YAML e `bash -n`: **PASS** |
| Diff e documentação | `git diff --check`, sintaxe Python e links locais: **PASS** |

Os 30 skips da execução geral são casos com outras dependências/variáveis específicas; não foram convertidos em evidência de aprovação. As suítes críticas de estoque, receitas e pedidos PostgreSQL foram executadas e verificadas pelo gate, sem skips. Houve uma rodada com falhas de inicialização de subprocessos Windows (`3221225794`); os 59 testes desse grupo passaram na repetição isolada e a suíte completa posterior passou. Não foi alterado teste para ignorar essa falha de ambiente.

### Evidência de banco

Foi provisionado PostgreSQL 15.13 portátil, descartável, restrito a `127.0.0.1:55432`, com usuário e bancos sintéticos. Não se utilizou configuração de conexão da aplicação nem banco produtivo.

1. **Banco vazio:** cadeia Alembic inteira aplicada ao head novo; consultas ORM e constraints reais exercitadas.
2. **Upgrade de clone:** dump/restore de baseline sintética no predecessor, seguido de upgrade. Saldo preservado: `40.000000`; valor histórico ponderado preservado: `1480.49382680000000`. Unidade legada continuou sem classificação inventada.
3. **Preflight adverso:** clone separado com `min_stock=0.1234567` foi recusado antes da alteração de schema; revision anterior, tipo Float e ausência das novas tabelas foram preservados pela transação.
4. **Concorrência:** sessões PostgreSQL independentes exercitaram reserva versus saída, confirmação duplicada e consumo compartilhado. Também foram testados lotes distintos, reserva de outro compromisso, cancelamento, compensação e isolamento entre tenants.
5. **Compatibilidade HTTP:** o endpoint antigo conservou números JSON, auditoria do ator autenticado e estorno idempotente sem apagar a entrada.

Relatórios locais ficam em `.runtime/gran-torino-f1-pg/`: `release-verified.xml`, `critical-release.xml`, `shell-retry.xml`, `migration-preflight-rejection.log` e `frontend-build-final.log`. São evidências locais ignoradas pelo Git, não aprovação de CI remoto. Os testes e workflows versionados permitem repetir a validação com bancos descartáveis próprios.

A instância PostgreSQL descartável foi encerrada ao fim da validação; seus artefatos sintéticos foram preservados para auditoria. Nenhum serviço PostgreSQL preexistente foi alterado.

Os testes não comprovam dados reais reconciliados, impressão física, homologação visual do novo painel ou operação na VPS. A entrega de desenvolvimento da F1 está concluída e validada localmente; esses gates de ativação permanecem explícitos.
