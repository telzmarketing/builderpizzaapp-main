# Campanhas Estratégicas — Progresso C0–C11

Última atualização documental: 2026-11-26

## Regras de acompanhamento

- `Aprovado` exige evidência funcional proporcional ao risco; testes isolados não aprovam, por si só, um fluxo administrativo, comercial ou operacional completo.
- Checkout, catálogo, preço, pagamentos, pedidos, estoque, CMV e KDS canônicos continuam sendo as autoridades. Campanhas Estratégicas não deve criar caminhos paralelos para esses domínios.
- Evidência local não equivale a homologação em PostgreSQL real, aceite autenticado, operação física ou publicação em produção.
- Nenhum deploy faz parte deste checkpoint documental; publicação do código não equivale a ativação em produção.
- Produção exige autorização expressa, SHA completo, release imutável, backup validado e aprovação dos gates C10.

## Estado consolidado

| Etapa | Escopo | Estado atual | Evidência confirmada | Pendências que impedem aceite integral |
|---|---|---|---|---|
| C0 | Baseline, contratos e matriz corretiva | Aprovado como especificação | Auditoria e contratos registrados; evolução aditiva e autoridades canônicas preservadas como critério | Manter a matriz sincronizada com mudanças de contrato |
| C1 | Lista administrativa e detalhe por campanha | Implementado; validação funcional pendente | Rotas e superfícies administrativas presentes; testes incluídos na suíte frontend consolidada | Validar sessão autenticada, estados vazio/erro/loading e navegação real |
| C2 | Gestão e composição de campanhas/ofertas | Implementado; validação funcional pendente | Backend, frontend, migrations e testes focados integram os 55 testes backend aprovados | Exercitar produto e combo até o checkout e reconciliar preço/restrições canônicos |
| C3 | Mídia e apresentação individual | Implementado; integração pendente | Upload e campos visuais integrados ao fluxo administrativo | Comprovar ownership tenant-scoped, upload real e renderização autenticada |
| C4 | Builder, versões publicadas, renderer e preview | Implementado; aceite autenticado pendente | Editor e renderer compartilhado; 17 testes frontend e matriz visual local de 360, 390, 430, 768, 1024, 1366 e 1920 px aprovados sem overflow horizontal | Validar edição/publicação com sessão e dados reais |
| C5 | Landing pública e configurador/checkout canônico | Implementado; E2E comercial pendente | Landing compartilhada e entrada no fluxo canônico | Demonstrar produto e combo completos até pagamento/pedido, sem preço paralelo |
| C6 | Slots, capacidade, bloqueios e reservas | Implementado em código; homologação transacional pendente | Backend e abas administrativas; lock, idempotência, limites, expiração e liberação cobertos localmente; UI responsiva inspecionada | Repetir concorrência/constraints com sessões independentes em PostgreSQL real |
| C7 | Pedido programado, pagamento e KDS canônico | Slice operacional implementado; ambiente real pendente | Reserva vinculada ao pedido; liberação idempotente pelo serviço KDS; cancelamento devolve capacidade uma vez | Validar scheduler, pagamento real, KDS físico, impressão, estoque, CMV, financeiro e retries quando aplicáveis |
| C8 | Funil, mídia, capacidade e resultados | Backend implementado; reconciliação/dashboard pendentes | Métricas, fontes/fórmulas, `null` para ausência e integração externa não bloqueante cobertas localmente | Validar dashboard, PostgreSQL representativo, mídia real e reconciliação financeira |
| C9 | RBAC, isolamento tenant e regressão | Implementado localmente; aceite integral pendente | Permissão dedicada de publicação; 55 backend, 17 frontend, typecheck, builds client/server e matriz responsiva aprovados | Executar E2E autenticado, PostgreSQL real, concorrência e integrações antes de produção |
| C10 | Release imutável e rollback seguro | Documentado; não executado | Runbook preparado; head Alembic `20261126_strategic_campaigns_c11` | SHA/CI, homologação, backup/restore, compatibilidade de rollback e autorização de produção |
| C11 | Ofertas por subcategoria, venda multicanal e unidade comercial agrupada | Implementação local concluída; homologação pendente | Contratos aditivos; snapshot publicado como autoridade; produto/kit/subcategorias; compositor compartilhado; grupo comercial; sold-out; reservas vinculadas atomicamente; adicionais pagos preservados | PostgreSQL real, concorrência, E2E autenticado nos canais, integrações KDS/estoque/CMV/financeiro e evidência visual real |

## Evidências consolidadas

- Backend focado C0-C11 e target Alembic: `76 passed` na rodada consolidada, seguida por `3 passed` nos reparos finais.
- Frontend focado: `20 passed`.
- TypeScript do recorte C11: aprovado. O typecheck global permanece bloqueado por erros sintáticos preexistentes e fora do escopo em `CrmAgenteWhatsApp.tsx`.
- Build do cliente: aprovado.
- Build do servidor: aprovado.
- Head Alembic único: `20261126_strategic_campaigns_c11`.
- Matriz visual pública: 360, 390, 430, 768, 1024, 1366 e 1920 px, com renderer e cinco ofertas presentes e `scrollWidth == clientWidth`.
- Matriz visual administrativa do editor: 390, 768, 1366 e 1920 px, sem overflow horizontal.
- Evidências visuais locais foram geradas pela matriz responsiva; artefatos temporários não fazem parte do pacote de produção.
- Nenhum deploy executado neste checkpoint.

Essas evidências comprovam somente a integração local coberta pelas suítes executadas. Não comprovam concorrência real do PostgreSQL, integrações externas, operação física ou funcionamento em produção.

## Gates bloqueantes antes da promoção

1. Aplicar a cadeia em PostgreSQL real descartável, em banco vazio e cópia representativa anonimizada, confirmando o head esperado.
2. Repetir concorrência de capacidade/reserva com conexões independentes, cobrindo lock, limite, idempotência, expiração, cancelamento e rollback por falha.
3. Executar E2E autenticado de RBAC e isolamento entre dois tenants, incluindo publicação negada/permitida e acesso cruzado.
4. Demonstrar produto e combo desde landing/configurador até quote, checkout, pagamento e pedido canônicos.
5. Quando aplicável ao piloto, validar pagamento, scheduler, KDS físico, impressão, estoque, CMV, financeiro e CRM/notificações, sem duplicidade em retry.
6. Executar CI e builds exigidos no SHA exato; os builds locais não substituem CI do pipeline.
7. Validar backup/restore e classificar o par de schema. Sem compatibilidade explícita, tratar o cutover como `forward-only`.
8. Obter autorização expressa, janela, responsáveis e critérios de abortar.

## Próximo checkpoint

Executar homologação controlada, sem promover produção: PostgreSQL real/concorrência, E2E autenticado/multi-tenant e integrações aplicáveis. Só então C9 poderá ser aprovado integralmente e C10 receber um SHA candidato.

O procedimento está em `docs/strategic-campaigns-release-runbook.md`.

## C11 - Matriz das melhorias funcionais

### Contratos preservados

- `ProductCategory` e `Product` permanecem como catálogo canônico; não foi criado catálogo paralelo.
- `Product.tsx` permanece como configurador de tamanho, sabores, massa, borda, adicionais e opções.
- `ManualOrderComposer` continua sendo a superfície compartilhada por PDV, Operações e atendimento WhatsApp.
- Quote e criação continuam entrando no `OrderService`; não existe checkout estratégico paralelo.
- Cada oferta composta é uma unidade comercial no carrinho/pedido, mas seus produtos continuam materializados individualmente para KDS, estoque e CMV.
- `entry_channel` registra onde a venda foi lançada sem substituir `order_origin`, `sales_channel` ou a atribuição de mídia.

### Requisitos incorporados

| Requisito | Implementação C11 | Gate de aceite |
|---|---|---|
| Botões dinâmicos no PDV e Fazer Pedido | Campanhas publicadas e comercialmente elegíveis são descobertas pelo tenant/canal e acrescentadas depois de Promoções | Duas campanhas aparecem sem alteração de código; campanha encerrada desaparece |
| Produto, combo, subcategoria e mescla | `reference_type` aditivo e componentes ordenados por subcategoria | Criar pela interface 2 tradicionais + 1 especial e republicar |
| Quantidade variável e configuração sequencial | Cada quantidade gera uma etapa que reutiliza o configurador de produto | Impedir etapa faltante, excedente ou produto de outra subcategoria |
| Percentual, desconto fixo e preço fixo | Estratégia persistida e recalculada pelo servidor com `Decimal` | Adulteração de preço do cliente é rejeitada; três fórmulas reconciliadas |
| Unidade comercial agrupada | Grupo comercial com snapshot e vínculo dos `OrderItem` reais | Remoção/quantidade afeta o grupo completo; KDS recebe cada produto |
| Disponibilidade e limite compartilhados | Consumo tenant-scoped por oferta/cliente e canal, com idempotência | Duas compras simultâneas da última unidade resultam em uma confirmação |
| Indicadores por canal | `entry_channel` separado da atribuição publicitária | Landing, PDV, Operações, telefone, WhatsApp e balcão reconciliados |
| Aparência Visual | Coluna visual existente preservada; mudanças limitadas ao contrato comercial e preview | Comparação visual autenticada desktop/mobile sem regressão |

## Atualização complementar — 2026-11-27

Os requisitos complementares foram auditados contra a implementação atual. Esta atualização é aditiva e não substitui o histórico C0–C11 acima. Não houve alteração de código nesta atualização documental.

### Status complementar

| Frente | Estado | Evidência atual | Bloqueio para aceite |
|---|---|---|---|
| Autenticação, cadastro e endereços | Parcialmente implementado | Fluxo canônico de sessão, login, registro, endereço e checkout existente | Carrinho/contexto de campanha ainda não têm restauração durável e E2E após login/registro/refresh. |
| Landing, configurador e checkout | Implementado como integração canônica | Landing, configurador, carrinho, quote, OrderService e pagamento são reutilizados | Falta prova autenticada completa e decisão sobre alias `/campanha/:slug` versus `/campanha-estrategica/:slug`. |
| Pagamentos | Parcialmente implementado | Pix/cartão, webhooks, idempotência e restrições comerciais existentes | Ciclo público de pagamento parcial, reserva, pendência, expiração, cancelamento e reembolso ainda não está fechado. |
| Agendamento | Parcialmente implementado | Políticas de lead time e loja aberta/fechada no domínio canônico | Checkout ainda usa `datetime-local`; falta disponibilidade pública com slots e bloqueios por modalidade. |
| Capacidade e reservas | Implementado no domínio administrativo; não integrado integralmente ao checkout | Serviço possui locks, limites, expiração, release e bind | P0: provar hold atômico e concorrência real antes de criar pedido/pagamento, inclusive canais compartilhados. |
| Automações WhatsApp por campanha | Ausente | Gateway, outbox, templates e automações globais existem | Faltam agregado estratégico, geração idempotente, precedência, editor, eventos e métricas por campanha. |
| CRM/histórico unificado | Parcialmente implementado | CRM, timeline e histórico geral existentes | Falta vínculo pesquisável de campanha/oferta/pedido/reserva/pagamento/agendamento/mensagem. |
| Dashboard de automações | Ausente | Dashboards globais e métricas comerciais/marketing existentes | Faltam programadas, enviadas, entregues, falhas, confirmações, lembretes e taxa por campanha. |
| E2E integral | Não comprovado | Testes focados de contratos, composição, capacidade e gateway existentes | Falta cenário autenticado e multicanal completo em PostgreSQL real, sem mensagens/cobranças reais. |

### Riscos P0–P2 e gates adicionados

- **P0 — capacidade:** duas sessões independentes devem disputar a mesma vaga/unidade e produzir no máximo uma confirmação; o gate exige PostgreSQL real, hold, bind, expiração, cancelamento e idempotência.
- **P0 — jornada autenticada:** login/registro/refresh não podem perder composição, campanha, desconto, UTM ou agendamento; o gate exige E2E de cliente existente e novo.
- **P1 — disponibilidade e pagamento:** slots devem ser gerados pelo backend e o estado financeiro/reserva deve permanecer correto em pendência, parcial, confirmação, expiração, cancelamento e reembolso.
- **P1 — automações:** nenhum envio sem evento persistido, vínculo de campanha e deduplicação; alteração de agendamento deve cancelar lembretes antigos e preservar o histórico.
- **P2 — operação e observabilidade:** landing, PDV e Operações devem compartilhar composição/preço/disponibilidade; CRM e dashboard devem usar fontes persistidas e respeitar tenant/RBAC/LGPD.

### Próxima fatia

O próximo checkpoint deve implementar e validar, nesta ordem:

1. snapshot durável e contrato de retorno da jornada de campanha após autenticação;
2. endpoint público de disponibilidade com datas, intervalos, bloqueios, modalidade e capacidade;
3. hold transacional integrado ao quote/checkout, bind ao pedido e release por expiração/cancelamento;
4. agregado aditivo de automação estratégica, geração idempotente e eventos de pedido/pagamento/agendamento;
5. editor, histórico, CRM e dashboard somente depois dos contratos acima estarem comprovados.

### Critério de avanço

Não promover esta frente para `Aprovado` por existência de rota, modelo ou teste isolado. O avanço exige evidências do fluxo inteiro, concorrência PostgreSQL, isolamento entre tenants, reprocessamento idempotente, builds/CI do SHA e validação visual autenticada. Falhas de WhatsApp devem permanecer fora da transação comercial e não podem cancelar checkout, pagamento ou produção.

### Evidência ainda obrigatória para concluir C11

1. Alembic upgrade em banco vazio e em cópia representativa, com head único e classificação de rollback.
2. Concorrência real no PostgreSQL para limite total, limite por cliente, idempotência, cancelamento e liberação.
3. E2E autenticado do cenário Black Friday integral pela interface administrativa, landing, PDV e Operações.
4. Reconciliação dos itens configurados com pedido, pagamento, financeiro, estoque, CMV, KDS e CRM.
5. Capturas reais das superfícies desktop e mobile; mocks isolados não aprovam este gate.
6. Regressão de produto, combo, promoção convencional e pedidos sem campanha.

Nenhum deploy em produção integra C11 nesta etapa.
## Atualizacao de validacao - 2026-11-27

Esta rodada implementou snapshot duravel do carrinho/contexto do cliente,
persistencia e exibicao das imagens desktop/mobile das ofertas, contrato publico
de disponibilidade C6 e o agregado C12 de automacoes WhatsApp por campanha.
As automacoes sao apenas definicoes idempotentes protegidas por RBAC nesta
etapa; nao houve envio real, editor, outbox, CRM ou dashboard especifico.

Evidencias: 13 testes backend focados aprovados, 16 testes frontend focados
aprovados, compileall, typecheck global e git diff --check aprovados. A cadeia
tem head unico `20261127_strategic_campaign_automations_c12`; a geracao offline
completa ainda esbarra em uma migracao historica que usa introspeccao de schema
incompativel com MockConnection, antes de chegar a C12.

O aceite integral continua pendente de PostgreSQL real, concorrencia de hold no
checkout, E2E autenticado/multitenant, eventos/outbox efetivos, integracao de
CRM/dashboard e validacao visual autenticada.
