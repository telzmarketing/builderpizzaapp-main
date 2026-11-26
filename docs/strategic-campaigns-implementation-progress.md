# Campanhas Estratégicas — Progresso C0–C10

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
| C10 | Release imutável e rollback seguro | Documentado; não executado | Runbook preparado; head Alembic `20261126_strategic_campaign_publish_rbac_c9` | SHA/CI, homologação, backup/restore, compatibilidade de rollback e autorização de produção |

## Evidências consolidadas

- Backend focado: `55 passed`.
- Frontend focado: `17 passed`.
- TypeScript typecheck: aprovado.
- Build do cliente: aprovado.
- Build do servidor: aprovado.
- Head Alembic único: `20261126_strategic_campaign_publish_rbac_c9`.
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
