# Gran Torino — Fase 0: contratos operacionais propostos

Data da revisão: 21/10/2026. Escopo desta entrega: documentação de KDS, preparo e planejamento. Documento complementar ao master `docs/GRAN_TORINO_FASE_0.md`, cuja matriz de fases 0–10 rege a sequência global. Nenhuma API, tabela, migration, configuração ou rotina operacional descrita como proposta está implementada por este documento.

## 1. Status e limites de aprovação

O Arquiteto revisou e define neste documento os contratos técnicos da Fase 0: identidades, rotas, schemas, estados, efeitos e limites transacionais. São o desenho proposto para implementação futura, sujeito ao aceite do usuário; não endpoints disponíveis. A autorização para produzir a Fase 0 não aprova automaticamente regras físicas do gestor, implementação, alteração de contratos existentes ou implantação. Valores de duração, validade, capacidade, tolerância de desconexão, margem e calendário precisam de configuração e validação do gestor.

O cadastro comercial continua em produtos; os ingredientes e itens preparados devem pertencer ao estoque canônico. As fichas existentes serão evoluídas. Não criar usuários, permissões, saldos, receitas KDS ou distribuição de entregadores paralelos.

## 2. Base real revalidada

| Evidência no código atual | Implicação |
| --- | --- |
| `client/App.tsx:623`, `:624`, `:632`: cozinha, expedição e visão geral KDS | Evoluir as superfícies existentes e integrar indicadores |
| `backend/routes/kds.py:13-52`: rotas e RBAC de cozinha | Manter `/api/kds/kitchen/...` como limite operacional |
| `backend/services/kds_service.py:190-210`: início muda para `preparing`, finalização atual para `ready_for_pickup` | Finalizar montagem precisa de etapa interna própria, sem redefinir o endpoint publicado de pronto |
| `backend/services/order_service.py:1111-1170`: autoridade de status, consumo e evento transacional | Não alterar status comercial fora de `OrderService`; revisar seus commits na futura composição transacional |
| `backend/services/order_service.py:864`, `:925`, `:1011-1013`: criação por sessão de mesa já em preparo, com snapshot e consumo | O bridge precisa cobrir salão, além das transições tradicionais de pedido |
| `backend/services/inventory_service.py:335-403`: consumo por pedido, lock, idempotência `order_sale`, snapshot CMV e validação de saldo | Reutilizar esta autoridade, substituindo granularidade progressivamente |
| `backend/services/inventory_service.py:406-441`: cancelamento após início registra `order_sale_loss`, delta zero | O código atual já evita devolução automática nesse caso; não apresentar isso como lacuna ainda não corrigida |
| `backend/services/inventory_service.py:448-469`: caminho de estorno quando não iniciado | Preservar diferenças entre liberação, estorno justificável e perda real |
| `backend/models/cmv.py:13-63`; `backend/services/order_service.py:796`, `:1011` | Já existem snapshots por pedido/item e referências de versões; avaliar extensão/projeção antes de outra persistência |
| `backend/services/recipe_resolution.py:25-78`, `:87-94` | Motor existente de frações, componentes e insumos; estender um único mecanismo |
| `backend/models/inventory.py:167-210`; `client/pages/admin/Products.tsx:593-729`, `:2540-2623` | Fichas oficiais com papel e fração e editor existentes |
| `client/pages/admin/Cozinha.tsx:9`, `:69`, `:74`, `:163` | Polling de 15 s e relógio visual de idade do pedido; não existe aqui temporizador individual de montagem |
| `backend/core/kds_station_access.py:8-24`; `backend/routes/admin_auth.py:138-139` | Conta de estação cozinha limitada ao prefixo de cozinha, mesmo que outro endpoint tenha RBAC permissivo |
| `backend/services/automation_event_producer.py:1-20`; `backend/services/automation_event_service.py:26-50` | Publicação persistente existente, deduplicada por tenant, dentro da transação do chamador |
| `backend/services/automation_event_service.py:73-107`, `:109-145` | Claim/lease e processamento voltados à materialização de automações; não são fan-out independente para consumidores KDS |
| `backend/core/events.py:230-270` | Bus síncrono em memória; não fornece entrega persistente entre workers |
| `backend/models/label.py:125-175`; `backend/routes/labels.py:16-24` | Impressão de expedição existente com origem pedido/item e auditoria; precisa de extensão para origem lote |

Referências correspondem ao checkout revisado, não constituem prova de implantação nem de estado do banco real.

## 3. Modelo operacional proposto

| Conceito | Identidade e regra |
| --- | --- |
| Grupo de produção | Tenant + pedido + revisão operacional; agrupa as unidades elegíveis para um operador no modo inicial por pedido |
| Unidade física | Tenant + item do pedido + índice entre 1 e quantidade; não dividir sabores de uma mesma pizza entre tarefas independentes |
| Tentativa de preparo | Unidade física + número de tentativa; retry técnico preserva tentativa; refazimento real cria outra com motivo e vínculo à anterior |
| Etapa | Montagem, forno quando aplicável, conferência e pronto; nem todo produto exige forno |
| Atribuição | Grupo/unidade + operador existente + versão + prioridade/posição; uma atribuição ativa por tarefa/tentativa |
| Sessão operacional | Tenant + usuário existente + estação, heartbeat e estado; sessão autenticada não prova disponibilidade |
| Preparação intermediária | Saída vinculada ao item de estoque existente, receita versionada de transformação e rendimento; sem segundo cadastro de insumos |
| Plano/revisão | Período/data de uso, produto/tamanho/canal, origem da demanda, aprovação e histórico |
| Ordem/execução de preparo | Programação aprovada, dependências, apontamentos parciais, lotes, responsável e transformação vinculada |

Persistência proposta canônica: `production_units` identifica a unidade por `(tenant_id, order_item_id, unit_index)` único; `production_attempts` identifica `(tenant_id, production_unit_id, attempt_number)` único e guarda etapas/composição/timestamps; `operational_composition_snapshots` e suas linhas guardam `(tenant_id, production_unit_id, revision)` único, com referências tenant-safe às versões imutáveis; `kds_operator_states` guarda disponibilidade/presença/versionamento por tenant/usuário/estação; `preparation_orders` guarda ordem e programação; `preparation_executions` guarda apontamentos incrementais e seus vínculos de transformação. Receitas de operação usam `inventory_operation_recipes` e referências versionadas definidas no master, sem fonte independente para KDS. Grupos e atribuições são vínculos operacionais das tentativas, sem duplicar `orders`/`order_items`. Database implementará estas identidades e constraints no desenho definido, sem segundo modelo concorrente. Identificadores novos exigem tenant obrigatório, referências consistentes entre tenants, índices de fila e unicidades no banco; locks sem constraints não bastam. O modo por unidade será habilitável posteriormente sem criar outro pedido comercial.

## 4. Estados e transições

### 4.1. Pedido e KDS

Preservar os contratos publicados de `OrderStatus`: `paid/pago → preparing → ready_for_pickup` e os caminhos existentes de entrega, retirada e salão. São referências reais em `backend/models/order.py:9-24` e `backend/services/kds_service.py:190-235`.

Estados internos PROPOSTOS da tarefa: `unassigned → queued → assembling → assembled → baking (se necessário) → checking → ready`. Cancelamento e bloqueio precisam de motivo e tratamento de consumo explícito. A transição `assembled` libera a capacidade de montagem do operador; forno não ocupa automaticamente o pizzaiolo.

O pedido fica `preparing` enquanto qualquer unidade obrigatória estiver incompleta. Só `OrderService` muda para `ready_for_pickup` após agregação de todas as unidades necessárias. O novo botão “Finalizar montagem” não chama o endpoint legado `/ready`. O endpoint publicado continua significando pedido pronto: no modo `legacy` mantém o contrato atual; no modo `attempts` exige todas as unidades prontas e retorna 409 `ProductionNotReady` em caso contrário. O gate é ligado ao regime persistido do pedido, nunca apenas à tela que chamou. Não ativar o regime novo para cliente legado sem compatibilidade validada.

Matriz KDS: `queued → assembling` por `start`; `assembling → assembled` por `finish-assembly`; `assembled → baking` por `start-oven` quando `requires_oven=true`; `baking → checking` por `complete-oven`; `assembled → checking` por `check` quando `requires_oven=false`; `checking → ready` por `check` aprovado. `check` reprovado deixa a unidade em `checking` com ocorrência e exige correção ou refazimento; nunca marca pronta silenciosamente. A operação `check` sem forno executa a passagem para conferência e o resultado da conferência atomicamente. As flags de etapa pertencem ao snapshot. Cada comando exige versão; etapas incompatíveis retornam 409. Cancelamento antes de consumo libera reserva; depois exige destinação auditada. Não existe reinício da mesma tentativa concluída: refazimento cria outra.

A modalidade inicial atribui todas as unidades do pedido ao mesmo operador. Itens que não exigem montagem devem ter política explícita de separação/conferência. Refazimento inicial é permitido somente enquanto o pedido comercial estiver `preparing`: retira a prontidão operacional da unidade afetada, preserva o histórico da tentativa anterior e mantém o pedido comercial em preparo. Não implica regressão de status comercial.

Limite explícito: `backend/core/state_machine.py:36-39` não permite `ready_for_pickup → preparing`, nem regressão a partir de `on_the_way` ou `delivered`. Para pedidos nesses estados, `remake` responde HTTP 409 `LateReworkNotSupported`, sem criar tentativa, movimentar estoque ou alterar pedido/entrega. A mesma restrição vale a retirada e salão; o caminho especial de conclusão desses atendimentos (`state_machine.py:170-174`) não autoriza retorno à produção. O bloqueio é verificado sob lock do pedido junto à criação da tentativa, evitando corrida com marcação de pronto/saída em rota. Uma futura ampliação de retrabalho tardio exige decisão específica do gestor na Fase 7, avaliação do Arquiteto e transição explícita por `OrderService`; nunca escrita direta do status. Consumos/perdas anteriores permanecem auditados, sem devolução automática.

### 4.2. Preparo antecipado

Estados canônicos da ordem: `draft`, `approved`, `scheduled`, `waiting`, `in_progress`, `paused`, `partially_completed`, `blocked`, `completed`, `cancelled`. Aprovação/programação não movimenta consumo definitivo por si só. Todas as transições abaixo exigem versão e auditoria; transições não listadas retornam 409.

| Origem | Comando / destino | Ator e efeito |
| --- | --- | --- |
| `draft` | `approve` → `approved` | Gestor com aprovação; congela composição/quantidade da revisão |
| `approved` | `schedule` → `scheduled` | Gestor com programação; define início, uso e dependências |
| `scheduled` | liberação por horário/dependências → `waiting` | Serviço canônico idempotente; sem baixa |
| `waiting` | `start` → `in_progress` | Preparador autorizado; registra início/responsável; consumo definitivo ocorre no apontamento físico |
| `in_progress`, `partially_completed` | `pause` → `paused` | Preparador responsável; registra motivo e início da pausa |
| `paused` | `resume` → `in_progress` | Responsável; fecha intervalo da pausa |
| `in_progress`, `partially_completed` | `reports` → `partially_completed` | Responsável; execução incremental com consumo/lote/perdas atômicos; quantidade total não conclui a ordem implicitamente |
| `in_progress`, `partially_completed` | `complete` → `completed` | Responsável; exige pendência zero e execuções reconciliadas |
| `scheduled`, `waiting`, `in_progress`, `paused`, `partially_completed` | `block` → `blocked` | Responsável/gestor ou validação de dependência; motivo obrigatório e `resume_state` preservado; não desfaz consumo |
| `blocked` | `unblock` → `resume_state` | Gestor ou serviço de dependência após revalidação; nunca inicia relógio ou consumo se estado anterior era `waiting` |
| `approved`, `scheduled`, `waiting`, `paused`, `partially_completed`, `blocked` | `reschedule` → mesmo estado | Gestor; altera datas sob versão, preserva execuções e revalida validade/dependências; não reinicia tarefa ativa |
| qualquer não terminal | `cancel` → `cancelled` | Gestor; motivo, destino das quantidades e fechamento de pendências explícitos; preserva lotes/efeitos já registrados |
| `completed`, `cancelled` | nenhuma transição de reabertura | Correção gera operação compensatória/ordem nova vinculada, autorizada, sem editar histórico |

`unblock` não retorna a `in_progress` sem confirmação do responsável quando o bloqueio interrompeu trabalho físico: nesse caso retorna `paused`, e `resume` retoma. Ao reprogramar quantidade após produção parcial, a quantidade-alvo não pode ficar abaixo da produção reconciliada. Encerrar abaixo do planejado exige redução aprovada de alvo com justificativa antes de `complete`; não ocultar pendência como perda. Regras físicas de registro durante mistura/resfriamento e descarte permanecem recomendação de produto a validar pelo gestor, sem lacuna no controle técnico de estados.

Apontamentos são incrementais e idempotentes. Programado 50 e produzido 47 deixa 3 pendentes; perda e descarte precisam de registro próprio. Quantidade aprovada pode diferir da produzida, com motivo. Cancelar uma ordem parcialmente executada não apaga produção ou consumo já confirmado.

## 5. Composição, versões, reservas e bridge de consumo

### 5.1. Snapshot coerente

Recomendação: congelar a composição aprovada do pedido, com referências de versões, tamanho, componentes comuns, frações, borda, adicionais, retiradas e substituições. Antes de persistir outra cópia, avaliar projeção/extensão dos snapshots CMV existentes, separando a saída operacional sem custos da visão financeira.

Reserva, consulta KDS e consumo devem usar a mesma revisão de composição, congelada antes de exibir a tarefa como executável ou reservar. A tentativa referencia essa revisão; nunca trocar silenciosamente por `recipe latest`. Não reservar com ficha A, mostrar ficha B e consumir ficha C. Uma consulta ao modal não cria reserva, não troca versão e não modifica pedido. Edição comercial posterior exige revisão explícita e invalidação/troca transacional das reservas ainda não consumidas; unidades iniciadas mantêm composição histórica. Resolver o significado operacional de mudanças em produção com o gestor antes de permitir esse fluxo.

Snapshot operacional contém quantidades/unidades normalizadas, versão de receita e regras de proporção; método/passos/imagem devem ser versionados ou referenciados de forma imutável. Imagem ausente não impede consulta. Notas livres não equivalem automaticamente a uma retirada estruturada: diferenças exigem destaque e confirmação no fluxo definido.

Reservas são compromissos de disponibilidade, não consumo. Políticas de momento da reserva, expiração e exceção por falta precisam de aprovação. Lotes aproveitáveis excluem vencidos/bloqueados e consideram validade na data de uso. Seleção/alocação efetiva precisa conciliar o snapshot com lotes e preparado disponíveis, sem trocar silenciosamente a composição.

### 5.2. Evento recomendado e pendência gerencial

Recomendação técnica para validação: “Iniciar montagem” confirma a retirada efetiva dos insumos da unidade/tentativa e registra consumo, timestamps e evento persistente na mesma transação. Esta equivalência precisa ser aceita pelo gestor; se o início no chão de fábrica não representa uso real, deve haver confirmação de consumo própria. Não escolher o momento apenas por conveniência de interface.

Finalizar montagem não debita novamente. Refazimento cria tentativa nova e consumo legítimo; retry da mesma tentativa retorna resultado anterior. Cancelamento antes de uso libera reserva; depois do consumo registra perda/destinação sem retornar automaticamente alimento ao estoque. Embalagens e outros componentes usados em etapa posterior precisam de evento real próprio por componente, sem duplicar ingredientes já consumidos na montagem.

### 5.3. Bridge legado obrigatório antes da ativação

Hoje o gatilho está em `OrderService.change_status` (`backend/services/order_service.py:1156-1159`) e também na criação por sessão de mesa (`:1011-1013`). O método legado identifica consumo por pedido, não por unidade/tentativa (`backend/services/inventory_service.py:335-403`).

Proposta de migração compatível:

1. Registrar por pedido qual regime o governa: legado ou unidade/tentativa. A ativação para novos pedidos não altera silenciosamente os já em produção.
2. Uma autoridade de estoque continua responsável pelos movimentos. Sob lock do pedido, ela escolhe um regime; nunca executa os dois para a mesma obrigação de consumo.
3. Pedido com movimentos `order_sale` existentes é reconhecido como já consumido. Vincular sua cobertura às unidades/tentativas iniciais exige reconciliação documentada; não gerar outra saída nem inventar lote histórico não registrado.
4. Para novos pedidos no regime por tentativa, o início da primeira unidade pode mudar status comercial para `preparing`, mas o gatilho antigo delega à mesma operação ou é desativado explicitamente para esse regime. Não chamar um método com commit intermediário e depois tentar tornar tarefa/estoque atômicos.
5. Salão, delivery, retirada, pedidos agendados e ações administrativas precisam passar pelo mesmo contrato. Não presumir que toda origem entra por `/kds/kitchen/...`.
6. Cancelamento/refund usa o regime e os movimentos reais. A proteção atual contra retorno após início deve ser preservada (`inventory_service.py:424-441`).
7. Não converter um pedido parcialmente consumido entre regimes sem plano de reconciliação. Desativar distribuição inteligente não desfaz consumo nem elimina tarefas.

O bridge mantém um escritor exclusivo por obrigação de consumo. Rollback de aplicação exige drenagem das tarefas do regime novo e verificação de compatibilidade: o código antigo não conhece lotes/tentativas e não pode reassumir esses pedidos apenas por trocar a versão implantada. Documentar recuperação e reconciliação antes da ativação.

Chave conceitual do novo efeito: `(tenant, unidade, tentativa, componente, tipo_do_efeito)`. A chave de transporte de uma requisição não substitui essa unicidade de negócio. Eventos repetidos e retries devem atingir a mesma obrigação; novo preparo atinge nova tentativa.

## 6. Planejamento e transformação

Necessidade líquida proposta: demanda prevista consolidada + segurança − saldo preparado aproveitável − produção confirmada com entrega no período. Cada parcela precisa usar unidade e horizonte consistentes. Pedidos firmes, promoção e previsão não podem ser somados se representam a mesma demanda.

Consolidar por revisão de plano e origem; meio a meio contribui proporcionalmente por sabor e uma única base. Registrar se a promoção já está incluída na previsão. Explodir preparações como dependências acíclicas, aplicar rendimento/perda técnica, lotes mínimos/máximos, embalagem comercial, antecedência, calendário e capacidade configurados. O motor comum de receitas é a base, sem fórmula própria em cada tela.

Fluxo: demanda/revisão → simulação de insumos e capacidade → proposta de ordens → aprovação → programação → execução parcial → transformação → lote aprovado → disponibilidade para consumo.

Cada transformação vincula saídas dos lotes de origem e entrada no lote preparado, custos, rendimento real e perdas em uma transação. Consumo futuro do preparado não volta a descontar o bruto. Conclusão de apontamento, lote e evento precisam confirmar juntos. Etiquetagem ocorre a partir do lote registrado, sem participar do efeito contábil de estoque.

Replanejamento cria revisão e identifica diferenças; não duplica ordens já aprovadas. Ordens em execução não são sobrescritas. Sugestões de compra consideram faltas líquidas sem emitir compra efetiva automaticamente. Fechamento diário reconcilia produção, consumo, perda, descarte e contagem física; ajuste requer permissão e justificativa.

## 7. Contratos de API PROPOSTOS

Estes são os contratos técnicos definidos na Fase 0 para implementação posterior. Rotas recebem/delegam/respondem; regras permanecem nos services. Todas as chamadas React passam por `client/lib/api.ts`. Alinhamento com o master: quantidades persistidas em `NUMERIC(20,6)`, custos em `NUMERIC(20,8)` e valores decimais transmitidos como strings nos DTOs novos; não converter contratos legados silenciosamente nem usar arredondamento binário do frontend como regra de negócio.

Comandos exigem header `Idempotency-Key` e corpo com `expected_version` inteiro não negativo. Não enviar `idempotency_key` no corpo. Escopo da chave: tenant + método/recurso normalizado; hash canônico e resposta são persistidos no commit do efeito. Replay reautoriza ator, retorna resposta original se hash igual e 409 `IdempotencyConflict` se diferente, sem novo efeito. Chave distinta não contorna unicidade de negócio. Tenant, ator e quantidades derivadas de receita não são campos editáveis em comandos KDS. `expected_version` é a versão do recurso da URL; para criação/simulação é 0, e aprovação de plano referencia a revisão vigente.

| Método e caminho proposto | Entrada / saída principal |
| --- | --- |
| `GET /api/kds/kitchen/orders/{order_id}/composition` | Retorna revisão, unidades, versões, frações, componentes comuns, modificações e instruções; sem custos ou dados privados de entrega |
| `GET /api/kds/kitchen/my-queue` | Fila do ator autenticado, atribuições e versões; nenhuma identidade de usuário confiada a query arbitrária |
| `POST /api/kds/kitchen/presence` | Estado solicitado e versão esperada; retorna estado operacional canônico |
| `POST /api/kds/kitchen/heartbeat` | Sessão operacional da estação; retorna hora do servidor e estado, sem inferir disponibilidade automaticamente |
| `POST /api/kds/kitchen/tasks/{task_id}/start` | `expected_version`; tarefa/consumo/relógio/evento confirmados juntos |
| `POST /api/kds/kitchen/tasks/{task_id}/finish-assembly` | Versão e idempotência; conclui montagem sem anunciar pedido pronto |
| `POST /api/kds/kitchen/tasks/{task_id}/start-oven` | Versão; registra entrada no forno, exige montagem concluída e etapa prevista |
| `POST /api/kds/kitchen/tasks/{task_id}/complete-oven` | Versão; registra saída do forno e envia à conferência, sem concluir pedido |
| `POST /api/kds/kitchen/tasks/{task_id}/check` | Versão, `approved` booleano e `reason` anulável obrigatório quando reprovado; confirma unidade ou registra ocorrência |
| `POST /api/kds/kitchen/tasks/{task_id}/remake` | Motivo e permissão adequada; apenas pedido `preparing`; cria tentativa distinta; demais estados retornam 409 sem efeito |
| `GET /api/preparation/orders` | Lista operacional autorizada por tenant, período e estado; escopo próprio de preparador |
| `POST /api/preparation/orders/{order_id}/start` | Versão e responsável derivado do ator |
| `POST /api/preparation/orders/{order_id}/reports` | Incrementos produzidos/aprovados/perdidos/descartados, lotes e motivos; retorna execução/lote/movimentos |
| `POST /api/preparation/orders/{order_id}/complete` | Fecha pendência zero, sem transformar diferença em perda implícita |
| `POST /api/preparation/orders/{order_id}/{command}` | `command` é `pause`, `resume` ou `block`; versão e motivo segundo matriz; três rotas distintas |
| `GET /api/preparation/orders/{order_id}/recipe` | Snapshot escalado da preparação e instruções operacionais sem custo restrito |
| `POST /api/gestao/preparation/orders` | Cria rascunho com preparação, snapshot/revisão, quantidade-alvo, unidade e datas |
| `POST /api/gestao/preparation/orders/{order_id}/{command}` | `command` é `approve`, `schedule`, `reschedule`, `unblock` ou `cancel`; versão e campos específicos da matriz; cinco rotas distintas |
| `POST /api/gestao/production-plans/simulations` | Horizonte, revisão de demanda e parâmetros versionados; retorna necessidades e conflitos, sem compras/produção efetivas |
| `POST /api/gestao/production-plans/{plan_id}/approve` | Versão e justificativa; aprova revisão e identifica ordens propostas sem duplicação |
| `POST /api/kds/management/redistributions` | Origem/destino, tarefas, versões e motivo; exige permissão gerencial específica |

Os endpoints operacionais deste documento seguem o envelope KDS de `backend/core/response.py:1-23`: sucesso `{"success":true,"data":...}` e erro de domínio `{"success":false,"error":{"code":"...","message":"..."}}`. Isso não impõe envelope aos endpoints de inventário com DTO direto. Autenticação e validação Pydantic preservam seu formato HTTP `detail` existente. HTTP: 201 criação de ordem/execução/tentativa; 200 leitura/comando de transição; 202 somente trabalho assíncrono já persistido; 403 permissão; 404 referência fora do escopo; 409 `VersionConflict`, `StateConflict`, `ProductionNotReady` ou `IdempotencyConflict`; 422 campos/quantidades/unidades/regras inválidos. Não revelar existência de IDs de outro tenant. Contratos publicados atuais não são renomeados.

### 7.1. Schemas e exemplos fechados para os três fluxos principais

Campos mostrados nos exemplos são obrigatórios, inclusive os explicitamente anuláveis; listas vazias são `[]`, nunca `null`. IDs são strings opacas não vazias; timestamps são RFC3339 UTC; datas de planejamento são datas locais do tenant. Decimais são strings base 10, sem expoente nem separador de milhar, com até seis casas para quantidade/fração; custos não aparecem nesses DTOs. Campos desconhecidos na entrada são rejeitados. `expected_version` é obrigatório em todo comando. `reason` é obrigatório não vazio para perda, descarte, bloqueio, refazimento, redistribuição e alteração administrativa.

**Iniciar uma unidade KDS.** `POST /api/kds/kitchen/tasks/task-1/start`, header `Idempotency-Key: start-task-1-v4`:

```json
{"expected_version":4}
```

HTTP 200; representação obrigatória da transição, com `consumption_operation_id` anulável apenas se a unidade não exige consumo ou já tem cobertura legada comprovada (`consumption_mode` distingue):

```json
{"success":true,"data":{"task_id":"task-1","group_id":"group-1","order_id":"order-1","order_item_id":"item-1","unit_index":1,"attempt_id":"attempt-1","attempt_number":1,"production_unit_id":"production-unit-1","composition_revision_id":"unit-composition-1-v1","state":"assembling","version":5,"operator_id":"user-1","started_at":"2026-10-21T21:00:00Z","assembly_finished_at":null,"consumption_mode":"attempts","consumption_operation_id":"operation-1","server_time":"2026-10-21T21:00:00Z"}}
```

`consumption_mode` é `attempts`, `legacy_covered` ou `not_required`. A operação de consumo é obrigatória no primeiro caso. A versão não muda no replay. `finish-assembly`, `start-oven`, `complete-oven` retornam a mesma identidade/versão/estado com timestamps atualizados; `check` acrescenta resultado de conferência auditado. `remake` exige `reason` e pedido `preparing`, referencia tentativa anterior e retorna 201 com tentativa nova `queued`, sem copiar consumo. Em outro estado comercial retorna 409 `LateReworkNotSupported`, sem iniciar a tentativa ou consumir seus insumos.

**Apontar preparo.** `POST /api/preparation/orders/preparation-order-1/reports`, header `Idempotency-Key: report-preparation-order-1-part-1`:

```json
{"expected_version":3,"produced_quantity":"47.000000","approved_quantity":"47.000000","discarded_quantity":"0.000000","output_unit_id":"unit-portion","input_allocations":[{"inventory_item_id":"raw-cheese","lot_id":"raw-lot-1","quantity":"14.100000","unit_id":"unit-kg"}],"losses":[],"reason":null,"prepared_at":"2026-10-21T12:00:00Z","storage_condition_id":"storage-1"}
```

`produced_quantity`, `approved_quantity`, `discarded_quantity` são incrementos, nunca totais acumulados, e não negativos; `produced = approved + discarded`. Uma quantidade produzida ainda não avaliada não é publicada como estoque aproveitável; deve aguardar aprovação antes do apontamento definitivo deste contrato. `input_allocations` é lista não vazia de insumos/lotes reais com quantidade positiva; o backend valida receita, rendimento e identidade da unidade, sem confiar nos IDs recebidos. `losses` aceita registros `{inventory_item_id, lot_id, quantity, unit_id, reason}` de perda de matéria-prima incluída no consumo total, sem debitar novamente o mesmo material; `discarded_quantity` classifica saída produzida rejeitada e não é somada como perda de insumo. `reason` pode ser nulo somente sem perda/descarte ou divergência de rendimento. Validade resulta da política versionada e do preparo, sem ser escolhida pelo operador; condição de armazenamento precisa pertencer à preparação.

```json
{"success":true,"data":{"preparation_order_id":"preparation-order-1","execution_id":"execution-1","version":4,"state":"partially_completed","planned_quantity":"50.000000","produced_total":"47.000000","approved_total":"47.000000","discarded_total":"0.000000","remaining_quantity":"3.000000","output_unit_id":"unit-portion","lot_id":"prepared-lot-1","expires_at":"2026-10-22T12:00:00Z","stock_operation_id":"transformation-1","completed_at":null}}
```

HTTP 201, ilustrativo: prazo do exemplo não define validade sanitária. `lot_id` é nulo quando aprovação é zero e não existe entrada aproveitável; `stock_operation_id` referencia a transformação auditável inclusive quando só houve descarte. Quantidades reais positivas precisam gerar operação. O relatório não declara automaticamente as três porções restantes perdidas. `complete` aceita apenas `expected_version` e exige pendência zero; cancelamento exige destino da pendência e justificativa.

**Composição operacional.** `GET /api/kds/kitchen/orders/order-1/composition`, HTTP 200:

```json
{"success":true,"data":{"order_id":"order-1","composition_revision_id":"composition-1","frozen_at":"2026-10-21T20:55:00Z","executable":true,"units":[{"production_unit_id":"production-unit-1","composition_revision_id":"unit-composition-1-v1","order_item_id":"item-1","unit_index":1,"product_id":"pizza-1","product_name":"Pizza ilustrativa","size_id":"size-1","size_name":"Grande","quantity":"1.000000","operator_id":null,"attempt_id":null,"requires_oven":true,"common_components":[{"inventory_item_id":"dough-1","name":"Massa","quantity":"1.000000","unit_id":"unit-piece","unit_symbol":"un","recipe_version_id":"recipe-base-v1","source_kind":"prepared"}],"flavors":[{"product_id":"flavor-1","name":"Sabor ilustrativo A","fraction":"0.500000","recipe_version_ids":["recipe-flavor-v2"],"ingredients":[{"inventory_item_id":"prepared-cheese","name":"Mu?arela porcionada","quantity":"0.150000","unit_id":"unit-kg","unit_symbol":"kg","recipe_version_id":"recipe-flavor-v2","source_kind":"prepared"}]},{"product_id":"flavor-2","name":"Sabor ilustrativo B","fraction":"0.500000","recipe_version_ids":["recipe-flavor-v3"],"ingredients":[{"inventory_item_id":"prepared-ham","name":"Presunto porcionado","quantity":"0.100000","unit_id":"unit-kg","unit_symbol":"kg","recipe_version_id":"recipe-flavor-v3","source_kind":"prepared"}]}],"removed_ingredients":[],"added_ingredients":[],"substitutions":[],"steps":[{"position":1,"instruction":"Montar conforme ficha aprovada","duration_seconds":null,"temperature_celsius":null}],"notes":null,"image_url":null}],"warnings":[]}}
```

O exemplo abrevia a segunda fração apenas para demonstrar schema: uma resposta executável real precisa conter todos os sabores e soma exata das frações igual a 1. Cada ingrediente de sabor/adicional/remoção usa o mesmo schema de componente, com quantidade efetiva; retirada tem quantidade efetiva `0.000000` e identificação do ingrediente removido. Substituição contém `removed` e `added` com esses componentes. `source_kind` é `raw`, `prepared` ou `packaging`; `recipe_version_id` é obrigatório. `steps.duration_seconds` é inteiro não negativo ou nulo; temperatura é string decimal ou nula. `size_id/size_name`, `operator_id`, `attempt_id`, `notes` e `image_url` são anuláveis. Unidade física sempre tem `quantity=1.000000`; quantidade comercial se expressa pela lista de unidades. `warnings` é lista de `{code,message}`. Revisão incompleta retorna `executable=false` e advertências, nunca instrução executável com frações inválidas. Este documento fixa schema; não autoriza dados incompletos em produção.

### 7.2. Campos dos comandos administrativos e operacionais restantes

Todos incluem `expected_version` e o header comum. `pause/block/cancel` incluem `reason`; `resume/unblock/approve/complete` não alteram quantidades. `schedule/reschedule` incluem `scheduled_start_at`, `planned_use_at` e `reason`; mudança de alvo em `reschedule` usa `planned_quantity` string opcional e passa pelas restrições de produção parcial. Criação de ordem exige `preparation_id`, `composition_revision_id`, `planned_quantity`, `unit_id`, `planned_use_at` e `reason` anulável. Alterações são substituições atômicas de revisão, não edição de execução histórica.

Simulação de plano exige `starts_on`, `ends_on`, `demand_revision_id`, `calendar_version`, `capacity_version`, `safety_policy_version`; resposta contém `simulation_id`, `version`, `requirements`, `proposed_orders`, `conflicts`, `input_versions`. Aprovação exige `simulation_id`, `expected_version` e `reason` anulável, revalida entradas e retorna `plan_id`, `approved_revision_id`, `preparation_order_ids` e `version`. Simulação obsoleta gera 409 sem emitir ordens. `presence` usa `requested_state` (`available`, `paused` ou `offline`), `station_id`, `reason` anulável e versão do estado; `heartbeat` usa `operational_session_id` e versão, devolvendo `server_time`, `state`, `version` sem reativação implícita. Redistribuição recebe `task_ids`, `task_versions` (mapa id→inteiro), `target_operator_id`, `reason` e versão da fila; todas as transferências confirmam juntas ou nenhuma.

## 8. Presença, temporizadores e distribuição

Estados de apresentação: offline, disponível, em produção, ocupado com fila e em pausa. A disponibilidade explícita é dado operacional; em produção/fila são projeções de execução e atribuições. Proibir que heartbeat por si só retire pausa ou recrie disponibilidade. Prazos e comportamento multiaba precisam de configuração/revisão; a identidade do operador é única, mesmo com várias conexões.

Servidor persiste `assigned_at`, `started_at`, intervalos de pausa quando permitidos, `assembly_finished_at`, `completed_at` e estimativa versionada. O browser calcula a apresentação a partir desses valores e da hora de referência do servidor; recarregar/modal/reconectar não reinicia relógio. Separar idade do pedido, espera e montagem. A estimativa restante nunca deve ficar negativa; atraso é indicador próprio, não estimativa de trabalho restante igual a zero por definição.

Distribuição inicial determinística, sem limite fixo de profissionais:

```text
abrir transação
serializar alocação por tenant/estação com lock transacional curto
carregar tarefas elegíveis por prioridade com envelhecimento, chegada e id
carregar operadores elegíveis e suas filas com locks em ordem estável
para cada grupo por pedido:
    reler cancelamento, versão e eventual atribuição ativa
    se já atribuído: não duplicar
    candidatos = disponíveis ou em produção/fila com capacidade de aceitar fila
    excluir offline, pausados e indisponíveis
    se há candidato sem montagem e sem fila:
        escolher última atribuição mais antiga; desempatar por id
    senão:
        carga = montagem restante + soma da montagem de toda a fila
        escolher menor disponibilidade prevista; desempatar deterministicamente
    se não há candidato: manter grupo na fila geral visível
    senão: inserir atribuição única, atualizar carga/versão e registrar evento
commit
```

Forno não compõe automaticamente a carga do pizzaiolo. Prioridades/capacidade e política para atraso acima da estimativa precisam de regra configurada. Não usar apenas um lock no candidato escolhido sem proteger a decisão de carga contra distribuições concorrentes. Inicio valida dono/estado/versão sob lock; duas sessões não iniciam a mesma unidade.

Redistribuir automaticamente apenas não iniciados. Desconexão transitória tem tolerância; execução ativa fica preservada e visível para intervenção, nunca abandonada implicitamente. Transferências explícitas auditam origem/destino/motivo. Aplicar intervalo mínimo e histerese para evitar filas oscilando sem ganho operacional.

## 9. Segurança e impressão

O endpoint de composição fica sob `/api/kds/kitchen/...` para respeitar o bloqueio real da estação (`backend/core/kds_station_access.py:23`). Não conceder inventário/CMV ao pizzaiolo para consultar receita. Reutilizar usuário, tenant, sessão e RBAC atuais; novas permissões precisam de provisionamento/versionamento próprio, sem segundo mecanismo.

Preparador exige superfície e permissões específicas. O prefixo canônico `/api/preparation/...` não é hoje permitido automaticamente a uma conta `cozinha`: a implementação deve provisionar papel preparador com permissão operacional e barreira própria para esse prefixo, sem acesso a `/api/gestao/preparation/...` ou `/api/gestao/production-plans/...`. Gerência usa permissões explícitas de aprovação/planejamento/redistribuição, nunca herdadas pelo papel operacional. Testar acesso por prefixo e por recurso; nunca abrir o prefixo gerencial a operadores.

Todas as consultas/ações validam tenant e propriedade operacional no backend. Operador recebe apenas os dados necessários; custos, compras, parâmetros administrativos e credenciais não integram payloads operacionais. Imagens seguem a propriedade de uploads do tenant e falham isoladamente.

Impressão reutiliza impressoras/templates/configuração, renderização e auditoria existentes (`backend/models/label.py:13-108`; `client/lib/labelPrinting.ts`). `LabelVersion.order_id` e `LabelVolume.order_item_id` hoje são obrigatórios (`label.py:132`, `:146`); prever extensão explícita para origem lote/execução, sem pedido fictício. Não afrouxar integridade das etiquetas antigas sem migration/desenho aprovado.

Etiqueta de preparo deriva do lote: produto, quantidade/peso, preparo, validade configurada, armazenamento, responsável e identidade do tenant. “Gran Torino” vem do tenant, não de constante global. Cópias por porção/recipiente/lote são parâmetros. Reimpressão registra motivo/ator sem movimentar estoque nem repetir produção. O estado existente `dialog_opened` (`label.py:159`) comprova diálogo solicitado/aberto, não impressão física; não prometer detecção de hardware sem integração correspondente.

## 10. Eventos persistentes e atualização

Reutilizar como ponto de partida `AutomationEventService.publish`: já persiste `automation_events` com `event_version`, agregados, correlação, causalidade e deduplicação por tenant (`backend/services/automation_event_service.py:26-50`). Publicar junto da mutação, sem commit autônomo no produtor, como documenta `automation_event_producer.py:1-5`.

Limitação concreta: `process_pending` altera um `status` global do evento e `_materialize_event` cria execuções de marketing (`automation_event_service.py:73-145`). Um consumidor KDS que apenas chamar esse claim concorre com automações e pode “roubar” eventos ou marcá-los processados antes dos demais. Também não há aqui confirmação/cursor independente para cada consumidor. Não anunciar fan-out multi consumidor como pronto.

Proposta sujeita a revisão arquitetural: evoluir o mecanismo canônico com entregas/cursors por consumidor, unicidade `(tenant, event_id, consumer)`, retry/lease e retenção; ou ponte única que distribua entregas persistentes a partir do evento original. Não implantar segundo outbox isolado ou reusar o status global para consumidores distintos. Versionar payloads e efeitos idempotentes; entrega pode se repetir, efeito de negócio não.

Contrato básico de eventos fechado na F0: `event_version=1`, `tenant_id`, `event_key`, `aggregate_type`, `aggregate_id`, `occurred_at`, `correlation_id` anulável, `causation_id` anulável, `dedupe_key` e `payload`. Chaves operacionais: `composition.revised`, `reservation.changed`, `production.assigned`, `production.started`, `production.assembly_finished`, `production.ready`, `preparation.reported`, `inventory.lot_produced`, `production.transferred`. Payload obrigatório contém `resource_id`, `resource_version` e `composition_revision_id` (nulo somente se o agregado não usa composição); conforme tipo, inclui `production_unit_id`, `attempt_id`, `preparation_order_id`, `execution_id`, `lot_id`, `from_operator_id` e `to_operator_id` anuláveis quando não aplicáveis. Não transmite custo/dados privados ao canal operacional. A especialização das entregas por consumidor pertence à fase futura de eventos, mantendo o envelope e sem usar o status global como ACK comum. Não depender de evento assíncrono para manter a atomicidade entre consumo e início que pertence à mesma transação.

O bus de `backend/core/events.py:230` continua inadequado como garantia de persistência. As telas atuais usam polling (`Cozinha.tsx:69`). Para evolução, avaliar um canal SSE autenticado para atualizações servidor→cliente, com cursor/reconciliação e suporte entre workers. O transporte é proposta; não existe por escrever este contrato. Em reconexão, consultar snapshot/revisão canônica; fallback ao polling não pode duplicar comandos. Nenhuma ação mutante é repetida automaticamente pelo cliente só porque caiu a conexão.

## 11. Fluxos e critérios de aceite futuros

1. **Consulta:** card → modal local → composição congelada → fechamento. Falha da receita ou imagem mantém pedido, relógio, fila e atualização operacionais; consulta não modifica estoque.
2. **Montagem:** disponibilidade explícita → atribuição → início confirmado → consumo uma vez → montagem finalizada → forno/conferência → agregação de prontidão → expedição. Duas sessões simultâneas resultam em uma execução e uma baixa.
3. **Refazimento/cancelamento:** retry não consome novamente; tentativa nova autorizada em pedido `preparing` consome de novo ao iniciar; cancelamento após consumo não retorna alimento automaticamente. Testar `remake` em `ready_for_pickup`, `on_the_way` e `delivered`: 409 `LateReworkNotSupported`, nenhum consumo/tentativa novos e nenhum retorno de estoque. Repetir para retirada e salão, preservando a conclusão especial existente sem regressão. Testar concorrência entre remake e pronto/saída de rota sob lock, garantindo um único resultado compatível. Evidenciar os dois regimes do bridge e consumos/perdas anteriores preservados.
4. **Preparo:** simulação → aprovação → programação → apontamento parcial → transformação atômica → lote → etiqueta. Erro em qualquer movimento desfaz toda a transformação; reimpressão deixa saldos iguais.
5. **Planejamento:** mesma revisão reprocessada não duplica ordem; promoção incluída não soma novamente; frações não duplicam base; lotes vencidos e reservas não são saldo livre.
6. **Distribuição:** profissional vazio é priorizado; ocupado é comparado por fila completa; nenhum candidato mantém fila geral; pausado não recebe tarefa; não existe teto fixo de operadores; tarefas iniciadas não migram automaticamente.
7. **Relógios:** modal/reload/restart mantêm início e duração; espera e montagem aparecem separadas; estimativas ruins são sinalizadas e não escondidas como carga nula.
8. **Permissões:** cozinheiro consulta composição sem CRUD/custos; preparador não altera plano; gestor redistribui com motivo; outro tenant não acessa IDs conhecidos; conta de estação mantém barreira de prefixo.
9. **Eventos:** rollback não publica evento persistente; retry produz um efeito; automações e consumidor operacional recebem suas próprias entregas; crash/restart não perde atribuição ou consome evento alheio.
10. **Compatibilidade:** pedido legado já baixado não sofre segunda baixa ao ativar novo KDS; endpoint de pronto não vira endpoint de finalizar montagem; entrega, retirada e salão mantêm contratos comerciais.

Validação futura precisa incluir PostgreSQL transacional/concorrência, contratos HTTP, cenários entre tenants, UI real em toque e impressão física quando fizer parte do aceite. Esta Fase 0 foi validada apenas por revisão estática dos caminhos citados e consistência documental, sem alegar execução desses testes.

## 12. Decisões pendentes do gestor e gates de implementação

Antes da fase executável, registrar aprovação das regras: evento real de retirada/consumo; instante de reserva e exceções; etapas por tipo de produto; item que exige conferência; prioridade/pausas/capacidade; tolerância de desconexão; validade e armazenamento; revisão comercial em produção; demanda promocional incluída/incremental; aprovação e ajuste de planos/ordens.

Pendência específica da Fase 7: definir se haverá retrabalho tardio após pedido pronto, em rota ou concluído e sua destinação operacional/financeira. Até decisão do gestor e avaliação arquitetural, o contrato inicial permanece restrito a refazimento em `preparing`; não declarar suporte a regressão do pedido ou entrega.

O desenho técnico F0 de identidades, constraints, estados, snapshots e contratos está definido neste pacote e revisado pelo Arquiteto. Nas fases de implementação, Database/Backend devem implementá-lo fielmente, ensaiar migrations/índices, remover commits intermediários incompatíveis com a transação definida e demonstrar reconciliação/rollback do legado. Impressão e entregas por consumidor evoluem nas fases correspondentes sob os limites aqui registrados. Nenhum parâmetro sanitário ou operacional é presumido aprovado por este documento.

A matriz de fases 0–10 e seus gates constam no master. Este complemento registra dependências operacionais: composição/snapshot e estoque canônico antecedem execução com consumo; transformação antecede planejamento que conte com preparado; tarefas/bridge antecedem distribuição por operador; multi consumidor persistente antecede transporte realtime confiável. Cada fase exige autorização própria e aceite verificável antes de expandir.
