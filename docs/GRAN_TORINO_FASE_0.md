# Gran Torino — Fase 0: baseline, decisões e contratos

Data: 21/10/2026 — America/Sao_Paulo.

## 1. Resumo executivo e escopo autorizado

Esta entrega executa a **fase 0 documental** do plano master de onze fases (0–10). Registra arquitetura, fontes oficiais, contratos propostos, backlog rastreável, critérios de validação e decisões pendentes. Não implementa funcionalidades, não publica contratos novos e não autoriza ativação, migration ou deploy das fases seguintes.

O usuário autorizou a execução desta fase. A aprovação de regras operacionais pendentes não é inferida dessa autorização. A definição pode ser concluída documentalmente com os bloqueios explicitados; a configuração/ativação afetada por um bloqueio permanece impedida até sua resolução.

### Pacote de definição

| Documento | Conteúdo |
|---|---|
| [Contratos de estoque e integração](GRAN_TORINO_FASE_0_CONTRATOS.md) | Recebimento, composição, unidades, lotes, reservas, consumo, financeiro e persistência |
| [Contratos operacionais](GRAN_TORINO_FASE_0_OPERACAO.md) | Preparo, planejamento, KDS, operadores, impressão e eventos |
| [Requisitos, aceite e gates](GRAN_TORINO_FASE_0_ACEITE.md) | Rastreabilidade dos cinco módulos, riscos, decisões do gestor e validação |

Todos os endpoints, campos e tabelas apresentados como novos nesses documentos são propostas de implementação futura. Exemplos usam identificadores e valores ilustrativos; não constituem cadastro real da pizzaria.

## 2. Baseline verificado

- Fonte: commit `4d553bf1e7678d65f22616b93c733fbb470afc2f`.
- Estrutura revisada: `backend/`, `client/`, `server/`, `shared/`, `tests/`, `docs/`, `scripts/`, `installer/`, `.github/` e papéis em `agents/`.
- Inspeção estática via AST de 144 arquivos de migrations: head único `20261020_inventory_recipe_fractions`, pai `20261020_product_order_options`, sem revisões-pai ausentes.
- Essa inspeção não importou o backend, não conectou ao banco e não comprova schema aplicado nem compatibilidade de runtime.
- Alterações preexistentes preservadas: `.claude/settings.local.json`, três worktrees em `.claude/worktrees/`, `backend/services/marketplaces/` e `tests/test_marketplace_contracts.py`.
- Contratos locais não rastreados de marketplaces não são evidência de integração publicada. A evolução precisa preservar os canais reais de venda, sem pressupor adapters operacionais não comprovados.

### Arquitetura real

| Área | Fonte e fato observado |
|---|---|
| Frontend | `package.json`: React 18, TypeScript, Vite, Tailwind; `client/App.tsx`: rotas; `client/lib/api.ts`: integração canônica |
| Backend | `backend/main.py`: registro de routers e ciclo de vida; `backend/requirements.txt`: FastAPI/Pydantic/SQLAlchemy/Alembic |
| Persistência | `backend/database.py`: sessões SQLAlchemy; `backend/migrations/versions/`: evolução de schema |
| Identidade | `backend/routes/admin_auth.py`, `backend/core/tenant_route_context.py`, `backend/core/rbac_authorization.py` |
| Catálogo | `backend/models/product.py`, `backend/models/order.py` e `backend/schemas/order.py` |
| Estoque e fichas | `backend/models/inventory.py`, `backend/services/inventory_service.py`, `backend/services/recipe_resolution.py` |
| Histórico de custo | `backend/models/cmv.py`, `backend/services/cmv_snapshot_service.py` |
| KDS | `backend/routes/kds.py`, `backend/services/kds_service.py`, `client/pages/admin/Cozinha.tsx`, `KdsOverview.tsx`, `Expedicao.tsx` |
| Documentos e financeiro | `backend/services/fiscal_service.py`, `backend/services/finance_service.py` |
| Impressão | `backend/models/label.py`, `backend/services/label_service.py`, `client/lib/labelPrinting.ts` |
| Eventos | `backend/core/events.py`, `backend/services/automation_event_producer.py`, `backend/services/automation_event_service.py` |
| Operação | `docs/UPDATE_TELZ_VPS.md`, `.github/workflows/deploy.yml`, `scripts/deploy-telz-from-origin.sh` |

Não há proposta de substituir o monólito por microserviços, criar outro catálogo ou trocar autenticação/RBAC. Rotas delegam a services; schemas validam entrada e saída; dados persistidos evoluem por Alembic; componentes React não calculam regras de negócio.

## 3. Fontes únicas e achados confirmados

| Domínio | Fonte oficial e comportamento atual | Evolução necessária |
|---|---|---|
| Produtos | `products`, opções e `order_item_flavors` | Preservar IDs; estruturar personalizações sem inventar gramagens |
| Insumos | `inventory_items`, unidades, fornecedores e locais existentes | Conversões, tipo preparado e políticas operacionais |
| Saldo | Soma de `inventory_stock_movements`; `inventory_service.py:592` | Lote/local/reserva; qualquer projeção deve ser reconstruível |
| Compra | `create_purchase`, `inventory_service.py:203` | Confirmação publica evento; não representa recebimento físico |
| Ficha | Versões e itens existentes; edição publica nova versão em `inventory_service.py:524` | Instruções, unidade, execução e personalização |
| Composição | `recipe_resolution.py:25`: quantidade × ocupação / referência | Decimal, frações explícitas e preparados, preservando legado |
| Consumo | `inventory_service.py:335`: somente `preparing`, com locks e idempotência | Unidade/tentativa, reserva e lote |
| Cancelamento | `inventory_service.py:406`: perda após início sem devolução automática | Destinação parcial e vínculo por tentativa |
| Snapshot | `cmv_snapshot_service.py:53`: também congela com controle de estoque ativo mesmo se dashboard CMV estiver desligado | Separar previsto de consumo/custo real por lote |
| Financeiro | `finance_service.py:482`: título por compra; vencimento usa `expected_date` ou data atual | Parcelas conferidas, obrigação vinculada e pendência explícita |
| Fiscal | Emissão interna a partir de pedido | Não tratar como importador de NF-e de entrada ou prova de autorização SEFAZ |
| Relógio KDS | `Cozinha.tsx:163`: idade desde criação; polling de 15 s | Relógio de montagem persistido e etapas internas |
| Eventos | Bus em memória e stream persistente de automação com estado global de processamento | Entrega independente por consumidor; não disputar o mesmo evento com workers incompatíveis |
| Precisão | `Float` em estoque/receitas/financeiro/fiscal/CMV | Expansão Decimal/Numeric com reconciliação |

Os achados da auditoria histórica em `docs/AUDITORIA_PRODUTOS_OPERACAO_2026-10-20.md` não devem ser reaplicados como defeitos atuais sem reprodução: o código de receitas e consumo já avançou. A revisão desta fase é estática; presença no código não equivale a teste funcional executado.

## 4. Registro de decisões arquiteturais

As decisões abaixo são definições técnicas da fase 0. Implementá-las continua dependendo da autorização da fase correspondente; regras de negócio pendentes não estão aprovadas.

| ID | Decisão técnica | Motivo / consequência |
|---|---|---|
| ADR-GT-01 | Evoluir catálogo, insumos, receitas e movimento existentes | Impedir fontes de verdade concorrentes |
| ADR-GT-02 | Manter ledger como autoridade do saldo | Reserva é compromisso separado; projeções são reconstruíveis |
| ADR-GT-03 | Distinguir compra, documento, recebimento e obrigação | Recebimentos parciais não repetem estoque ou dívida |
| ADR-GT-04 | Usar uma identidade de operação física permanente | Chave HTTP com expiração não basta para deduplicar fatos de negócio |
| ADR-GT-05 | Representar unidade vendida e tentativa de execução | Retry reutiliza tentativa; refazimento cria outra; itens comerciais não são duplicados |
| ADR-GT-06 | Separar composição congelada, consumo real e custo gerencial | Modal e baixa precisam concordar; CMV não controla fluxo de cozinha |
| ADR-GT-07 | Preservar referência histórica 1 e exigir meia pizza explícita | Alterar default do cadastro não pode dobrar receitas existentes |
| ADR-GT-08 | Transformar bruto em preparado no mesmo ledger | Consumo preparado não volta a baixar matéria-prima |
| ADR-GT-09 | Tenant obrigatório nas novas entidades e FKs tenant-safe | Não assumir `NOT NULL`/backfill global correto para legado sem auditoria |
| ADR-GT-10 | Decimal/Numeric nos novos contratos internos e expansão controlada do legado | Não alterar tipos/payloads publicados silenciosamente |
| ADR-GT-11 | Preservar estados comerciais; etapas de montagem/forno ficam na execução | `ready_for_pickup` continua significando pedido efetivamente pronto |
| ADR-GT-12 | Distribuir por pedido inicialmente, rastrear por unidade | Evolução posterior por pizza sem remodelar a venda |
| ADR-GT-13 | Reutilizar stream persistente após ampliar entrega por consumidor | Bus em memória não garante recuperação; sem novo broker obrigatório |
| ADR-GT-14 | Reutilizar RBAC, ACL de arquivos e barreiras KDS | Consulta técnica não concede custos/CRUD do estoque |
| ADR-GT-15 | Reutilizar impressão com origem lote/preparo explícita | Não criar pedido fictício para satisfazer FK; diálogo não comprova impressão física |
| ADR-GT-16 | Evolução expansiva, flags por tenant e migração forward | Rollback não apaga consumo/auditoria e não permite reativar escritor incompatível |

### Decisão sobre tempo de consumo

O desenho recomendado reserva antes e consome no início explícito da montagem por unidade/tentativa. **A equivalência entre clicar Iniciar e usar fisicamente os insumos depende do gestor.** Enquanto pendente, o comportamento `preparing` atual não muda. O desenho suporta outra confirmação física sem alterar a identidade da operação; o contrato aprovado deverá indicar um único evento autoritativo.

### Coerência da composição

Uma composição operacional deve ser congelada antes de ser apresentada como executável ou usada para reservar/consumir. A tentativa referencia essa revisão. Alteração posterior cria revisão explícita, invalida reserva ainda não consumida e exige nova confirmação; nunca recalcula silenciosamente o passado. O snapshot comercial/CMV atual é preservado. Produtos legados sem ficha continuam seguindo política existente até migração explícita; ficha parcial não é tratada como completa.

O desenho de persistência F0 distingue `production_units` (item comercial + índice da unidade), `production_attempts` (unidade + tentativa) e `operational_composition_snapshots`/linhas (revisão congelada), com vínculos tenant-safe. Unidade tem identidade estável mesmo após refazimento; snapshot operacional não substitui nem reprecifica o snapshot comercial/CMV. Receitas de preparo evoluem as versões existentes com `recipe_kind` e alvo exclusivo produto comercial ou insumo de saída, incluindo rendimento obrigatório de preparo. O detalhe dos CHECKs e unicidades consta no contrato de estoque.

O contrato inicial de refazimento opera enquanto o pedido está `preparing`. Refazimento após prontidão, saída para entrega ou conclusão depende de regra específica e evolução aprovada das transições; não regredir status comercial diretamente nem contornar o `OrderService`. Esse limite e os casos tardios são gate da fase 7, não uma capacidade que esta documentação declare já coberta pelo código.

### Convenções de API fechadas para a especificação F0

| Área nova | Base proposta | Convenção |
|---|---|---|
| Estoque | `/api/gestao/inventory/v1` | DTO direto; strings decimais nos DTOs novos, sem mudar contratos publicados |
| Preparo administrativo | `/api/gestao/preparation` | Comandos administrativos com autorização específica |
| Preparo operacional | `/api/preparation` | Superfície limitada do preparador, sem ampliar a conta cozinha atual |
| Planejamento | `/api/gestao/production-plans` | Simulação, revisão e aprovação separadas de execução |
| KDS cozinha | `/api/kds/kitchen` | Envelope `ok` existente e barreira de estação preservados |
| KDS gerência | `/api/kds/management` | Gestão/redistribuição autorizada; não aberta ao papel cozinha |

`Idempotency-Key` é header de comando; `expected_version` pertence ao corpo. Nenhum desses campos escolhe tenant ou ator. Estoque já retorna DTO direto, enquanto KDS usa `success/data`; não padronizar retroativamente esses contratos nesta iniciativa. Erros de domínio usam `err(DomainError)`; erros de autenticação e validação podem seguir `detail` existente. As propostas detalhadas dos anexos são a referência de implementação futura, não rotas publicadas.

## 5. Limites transacionais e recuperação

1. Resolver ator e tenant a partir do contexto confiável. Corpo não escolhe o tenant.
2. Verificar chave de requisição, identidade permanente da operação e versão esperada.
3. Bloquear a raiz da operação (pedido/execução/recebimento) e recursos em ordem estável; o desenho detalhado deve garantir a mesma ordem em todos os escritores.
4. Revalidar composição, quantidade, disponibilidade, condição do lote e versão dentro da transação.
5. Persistir movimentos, alocações, reserva consumida/liberada, execução e evento durável na mesma transação. Services subordinados não podem fazer commit intermediário.
6. Confirmar apenas uma vez no serviço que coordena a unidade de trabalho.
7. Integrações posteriores usam entrega recuperável e consumidor idempotente. Falha não é ocultada como sucesso financeiro.
8. Repetição retorna o resultado anterior; chave reaproveitada com outro conteúdo é conflito. Refazimento legítimo exige nova tentativa, não chave aleatória para contornar deduplicação.

A integração atual contém services com `commit` próprio. Sua composição transacional exige refatoração interna limitada e testes na fase correspondente; não basta chamar esses métodos em sequência. `OrderService.change_status` mantém a autoridade das transições, com refatoração compatível se necessária para participar da mesma unidade de trabalho.

## 6. Plano executável das fases seguintes

| Fase | Pacote | Dependência e gate principal |
|---|---|---|
| 0 | Baseline e contratos | Documentos consistentes; pendências declaradas |
| 1 | Precisão, autorização e fundação do estoque | Decimal reconciliado, tenant e writers inventariados; lotes/reservas/locks definidos |
| 2 | Fichas e composição | Frações e personalizações verificadas; versões e fonte única |
| 3 | Recebimento XML e financeiro | Operações idempotentes; obrigação separada do recebimento |
| 4 | Validade, FEFO e etiquetas | Regra de validade aprovada; lotes elegíveis e impressão sem movimento |
| 5 | Execução PCP e transformação | Receita/rendimento aprovados; bruto/preparado atômicos |
| 6 | Consulta técnica KDS | Mesma composição congelada, DTO sem custo, nenhum efeito colateral |
| 7 | Unidade/tentativa e multioperador | Evento de consumo aprovado; corte exclusivo dos escritores e agregação de prontidão |
| 8 | Planejamento semanal e reposição | Calendário, validade, capacidade e demanda sem duplicação |
| 9 | PDF, câmera e OCR | XML estabilizado; política de documentos e fornecedor aprovados |
| 10 | CMV efetivo e consolidação | Consumo real reconciliável e qualidade dos indicadores explícita |

Fluxos de compra, checkout, salão, WhatsApp, pagamentos, pedidos, cozinha, expedição, retirada e entrega entram na regressão quando afetados. Integrações somente documentadas/localmente não rastreadas exigem evidência própria.

## 7. Segurança e precisão

- Autorizações no backend por ação, não apenas por papel/tela. Não reaproveitar uma permissão ampla de estoque para liberar ficha ao pizzaiolo.
- DTO público permite nomes autorizados, sem quantidades, custos, fornecedores, lotes ou saldos, inclusive campos aninhados.
- Documentos fiscais e referências técnicas privadas usam ACL e ownership; novos uploads documentais não herdam exposição pública de imagem.
- Não converter massa em volume sem densidade; embalagens variáveis exigem peso/volume conferido.
- Quantidades físicas inteiras (unidades vendidas, tentativa, posição) continuam inteiras; frações racionais/decimais têm validação própria.
- Proposta inicial: `Numeric(20,6)` para quantidades e `Numeric(20,8)` para custos unitários; valores de títulos em centavos/duas casas, com rateios de alta precisão e residual determinístico. São escalas técnicas de partida, sujeitas à análise de limites antes da migration.
- Novos DTOs representam decimais como strings canônicas. Contratos publicados atuais permanecem com o formato existente até estratégia compatível/versionada ser aprovada. Não passar Decimal pela codificação atual presumindo preservação automática de precisão.

## 8. Implantação e rollback

O procedimento operacional vigente a usar como base é o fluxo imutável Telz, em `docs/UPDATE_TELZ_VPS.md` e scripts/workflows associados. Referências antigas a `git pull`, serviços `moschettieri-*` ou diretórios legados não são autorização para executar um procedimento diferente. Esta fase não altera essas referências nem executa qualquer operação na VPS.

Cada fase futura exige migrations ensaiadas em PostgreSQL descartável (do zero e com dados legados), CI no SHA exato, backup/restore ensaiado, release imutável, observação do tenant piloto e validação autenticada. Head Alembic e `/health` isolados não comprovam funcionamento.

Após a primeira operação com lote/Decimal/tentativa, o retorno a um escritor antigo pode corromper a reconciliação. Flags devem separar leitura, novos comandos e drenagem de execuções existentes. Não desligar o novo escritor e permitir consumo legado sobre a mesma tentativa. Se o código anterior não suportar o schema e os fatos novos, usar correção forward ou janela coordenada de recuperação, sem downgrade destrutivo.

## 9. Critério de saída da fase 0

| Gate | Evidência requerida |
|---|---|
| G0-01 | Baseline e estrutura reais registrados, sem confundir banco/VPS com fonte |
| G0-02 | Cinco módulos mapeados a reutilização, lacuna e fase |
| G0-03 | Contratos propostos de operação/API/erro/tenant/idempotência documentados |
| G0-04 | Composição, consumo, transformação, estados e cortes compatíveis definidos |
| G0-05 | Decisões do gestor identificadas com efeito sobre ativação, sem aprovação presumida |
| G0-06 | Matriz de aceite e testes obrigatórios, incluindo ausência de skips críticos |
| G0-07 | Revisão cruzada dos documentos, links/evidências existentes e diff restrito à documentação |

Cumprir esses gates conclui a entrega documental. Não significa F1 implementada, regra operacional aprovada, CI executada ou produção validada. O resultado da revisão final é registrado pelo Orquestrador na resposta de entrega.

## 10. Fora do escopo desta execução

Código de aplicação, endpoints, dependências, alterações em workflows, migrations, bootstrap, dados de produção, geração de estoque inicial, testes que criem banco, builds, flags, restart, commit/push e deploy. Não há autorização implícita para essas ações na execução da fase 0.

## 11. Registro de validação documental — 21/10/2026

Orquestrador e agentes de Arquitetura/Database/Backend, Operação/Frontend e Product Owner/QA revisaram o pacote. G0-01 a G0-07 atendidos no escopo documental; entrega técnica F0 concluída, com aceite do gestor e decisões de negócio pendentes explicitamente preservados.

Verificações executadas sem importar a aplicação ou conectar ao banco:

- Grafo estático de 144 migrations: um head e nenhum pai ausente.
- Quatro documentos UTF-8, delimitadores de blocos balanceados e ausência de whitespace final/caractere de substituição.
- Quinze exemplos JSON parseados com sucesso; composição ilustrativa revisada para duas frações cuja soma é 1.
- Quarenta e três requisitos com identificadores únicos e rastreabilidade para os cinco módulos e dependências.
- Links locais e referências de caminhos verificadas contra os arquivos existentes; `backend/.env`, citado apenas como exemplo de origem de credenciais a não reutilizar em testes, foi excluído da checagem de evidências.
- Revisão cruzada de bases de API, formatos reais de resposta, header de idempotência, snapshots, unidades/tentativas, estados, FEFO e divisão de movimentos entre lotes.
- Conferência de Git: entrega restrita aos quatro documentos novos; alterações preexistentes em `.claude` e arquivos de marketplaces preservadas. Nenhum arquivo de aplicação ou migration editado nesta fase.

Essas verificações validam a especificação, não a execução futura. Não foram executados pytest/Vitest, typecheck/build, testes HTTP/navegador, consultas ao banco, migrations, CI remoto, impressão física ou procedimentos na VPS. O gate de testes PostgreSQL ignorados no CI permanece backlog da implementação, não foi corrigido por documentação.
