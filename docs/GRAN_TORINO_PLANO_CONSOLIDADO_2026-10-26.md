# Orquestrador — Plano consolidado dos três prompts Gran Torino

Data: 26/10/2026. Revisão 2 após alinhamento operacional. Natureza: auditoria técnica e planejamento, sem implementação de produto.

## 1. Resumo Executivo

Os três pedidos foram analisados em conjunto: (P1) KDS Preparo, Pizzaiolo, Expedição e distribuição de entregas, conforme anexo; (P2) venda manual desktop/mobile, impressão, porcionamento, comprovantes, bebidas e pagamentos; (P3) visitantes públicos e instalação do aplicativo Motoboy.

**Conclusão:** a base já contém grande parte das entidades necessárias. A entrega exige completar integrações, corrigir contratos e fechar garantias transacionais antes de expandir as telas. Não se recomenda criar outro catálogo, estoque, cadastro de clientes, sistema de etiquetas ou máquina comercial de pedidos.

Esta revisão fecha as principais regras operacionais discutidas: a confirmação do pizzaiolo terá contagem regressiva de cinco segundos; a reserva/consumo será decidido pelo servidor ao término da contagem; falta de insumo abrirá uma exceção para atendimento e gerência; a Expedição não terá responsabilidade sobre pagamento; a entrada de estoque definirá quais produtos exigem porcionamento; e os quatro ambientes terão URLs e contratos próprios.

Esta revisão substitui suposições antigas por inspeção do checkout atual. Documentos de fases anteriores são referências, não evidência automática de funcionamento. Em particular, o código atual já implementa consumo por tentativa KDS, embora `GRAN_TORINO_FASE_8_QA.md` descreva uma revisão anterior em que essa integração ainda não estava comprovada. O problema atual inclui a coexistência desse consumo com o consumo legado por pedido.

### 1.1 Escopo da evidência

- Revisados estrutura, registro de rotas, componentes, contratos de API, serviços, modelos, migrations, documentação operacional e testes relevantes aos três prompts.
- Arquitetura confirmada: React 18/TypeScript/Vite/Tailwind; API canônica em `client/lib/api.ts`; FastAPI/services/SQLAlchemy; PostgreSQL/Alembic; Node para aplicação web; infraestrutura versionada em `installer/`, `scripts/` e `.github/`.
- Áreas percorridas: `client/`, `backend/`, `server/`, `shared/`, `tests/`, `docs/`, `public/`, configuração PWA e instruções em `agents/`.
- Referência Git local: `c8b9dc9`. Nenhum acesso à VPS, banco produtivo, sessão autenticada da pizzaria ou impressora física foi realizado.
- O head Alembic local é único: `20261022_receipt_pdf_camera_evidence`. Isso comprova a cadeia disponível no checkout; não comprova migrations aplicadas no banco real.
- Alterações preexistentes preservadas: `.claude/settings.local.json`, três worktrees, `backend/services/marketplaces/` e `tests/test_marketplace_contracts.py`. Os dois últimos estão não versionados; não são prova de conectores publicados.

### 1.2 Inventário e classificação

| Área | O que existe | Diagnóstico / ação |
| --- | --- | --- |
| Operações | `/painel/orders`, listagem, status, impressão e atribuição | Não foi localizado composer completo de venda manual; adicionar entrada desktop e mobile compartilhada |
| Clientes | Cadastro, identidade por telefone e listagem autenticada | Evoluir pesquisa paginada e cadastro mínimo; hoje o schema de criação exige e-mail |
| Catálogo e preços | Produtos, opções, variantes, sabores, orçamento, regras de frete/cupom | Reutilizar motor comercial; até três sabores conforme configuração vigente |
| Consumo no local | Mesas/comandas e materialização de pedidos | Reutilizar domínio salão; não substituir por um checkout independente |
| Pagamentos | Método, situação, provedor, pagamento na entrega e valor entregue em dinheiro | Corrigir projeções e apresentação; pagamento misto não está modelado |
| KDS Pizzaiolo | Tela atual Cozinha e componente multioperador | Parcial; alinhar contratos, inicialização, atribuição e agregação de unidades |
| Unidades e forno | `production_units`, `production_attempts`, timestamps e comandos de forno | Parcial; criação automática e gates incompletos; inicialização atual marca todos os itens como exigindo forno |
| KDS Expedição | Tela e serviço por pedido, etiquetas e atribuição de motoboy | Falta embalagem individual, checklist persistido e conclusão independente |
| Cozinha Preparo | Receitas operacionais, ordens e execuções; painel na aba Estoque | Parcial e incompatível entre frontend/backend; não transforma estoque ao apontar |
| Estoque | Ledger, receitas versionadas, Decimal na fundação, lotes, FEFO, reservas e genealogia | Completar transformação e regime exclusivo de consumo; não criar saldo paralelo |
| Etiquetas | Múltiplas impressoras, templates, volumes, versões, histórico e reimpressão | Reutilizar; ampliar origem para preparo/lote e transporte físico |
| Impressão em rede | IP, porta e protocolo cadastráveis | Cadastro é metadado: saída atual é `window.print`, sem conector de rede comprovado |
| Comprovantes | Completo/cozinha/entrega, prévia, teste, 58/80 mm e A4 | Evoluir os templates com logo tenant, bebidas, pagamento e troco |
| Distribuição pizzaiolos | Presença, heartbeat e redistribuição manual | Automação e disponibilidade efetiva incompletas |
| Distribuição motoboys | Serviço de autoatribuição e fluxo de coleta/entrega | Acionamento encontrado por endpoint; falta gatilho durável, elegibilidade completa e estado retornando |
| Atualização KDS | Polling de aproximadamente 10–15 segundos | Reaproveitar reconciliação; acrescentar entrega de eventos recuperável para atualização imediata |
| Visitantes | Eventos/sessões, identidade em localStorage e exclusão de `/painel`/`/motoboy` | Correção parcial existente; falta limitar positivamente à loja e medir presença ativa |
| PWA Motoboy | Botão na página Motoboy, manifest e worker | Botão está localizado, mas registro e metadados globais podem oferecer aplicativo fora da rota |

Há duas telas operacionais centrais já identificadas como cozinha e expedição, além do painel geral KDS e da TV de motoboys. O painel geral e a TV são visões de acompanhamento, não substitutos dos três postos solicitados. Preparo existe parcialmente dentro do estoque e precisa de entrada operacional própria.

### 1.3 Achados prioritários com evidência

| ID | Achado confirmado por inspeção | Evidência principal |
| --- | --- | --- |
| A01 | Consumo legado e consumo por tentativa têm identidades distintas; seu uso combinado pode repetir a baixa | `order_service.py:1156,1274`; `inventory_service.py:391`; `kds_production_service.py:80,110` |
| A02 | Expedição considera `!pay_on_delivery` como pagamento confirmado, sem consultar situação financeira | `client/pages/admin/Expedicao.tsx:26`; `backend/services/kds_service.py:526` |
| A03 | Pagamento fica oculto para retirada; valor de troco efetivo não é apresentado | `Expedicao.tsx:159`; `backend/models/payment.py:82` |
| A04 | Rotas genéricas de preparo precedem `/reports` e `/complete`; payloads e URLs divergem da interface | `backend/routes/preparation.py:23`; `client/lib/api.ts:8306`; `PreparationOperationsPanel.tsx:39`; `preparation_service.py:23` |
| A05 | Apontamento registra quantidade, mas não saída de insumo, entrada de preparado, lote ou operação de estoque | `backend/services/preparation_service.py:58`; `backend/models/preparation.py:77` |
| A06 | Fila retorna `task_id`, interface espera `id`; presença/redistribuição também divergem | `kds_production_service.py:31`; `client/lib/api.ts:1236,1445`; `KdsMultiOperatorBoard.tsx:109` |
| A07 | Inicialização unitária depende de endpoint explícito e fixa `requires_oven=True` para todos os itens | `kds_production_service.py:32`; `backend/routes/kds.py:32` |
| A08 | Caminho de pronto por pedido não agrega/verifica conclusão de todas as unidades | `kds_service.py:308`; `order_service.py:1110`; `Cozinha.tsx:105` |
| A09 | Autoatribuição aceita pedidos em preparo, não distingue integralmente modalidade/frota e não tem gatilho de expedição | `delivery_service.py:1292`; `backend/routes/delivery.py:599` |
| A10 | Reserva genérica não tem as mesmas garantias do caminho KDS; entregador possui apenas available/busy/offline | `delivery_service.py:178`; `kds_service.py:375`; `backend/models/delivery.py:37` |
| A11 | Abrir diálogo é o último estado de impressão; não confirma envio, conectividade ou papel impresso | `backend/models/label.py:154`; `client/lib/labelPrinting.ts:116`; `LabelSettingsPanel.tsx:83` |
| A12 | Novo checkout gera novo UUID; não há deduplicação transacional de criação por reenvio | `backend/services/order_service.py:625`; `backend/schemas/order.py` |
| A13 | Rastreamento exclui só prefixos internos conhecidos; presença é inferida de eventos recentes | `client/lib/tracking.ts:7,202,273`; `client/App.tsx:290`; `backend/routes/marketing.py:519,744` |
| A14 | TTL difere entre indicadores: dashboard Marketing usa cinco minutos; BI e tráfego leem configuração | `marketing.py:743`; `business_intelligence_service.py:865`; `paid_traffic_service.py:369` |
| A15 | PWA é injetado globalmente; HTML tem título Apple Motoboy e build local registra worker em `/` | `vite.config.ts:29`; `index.html:10`; `dist/spa/registerSW.js:1`; `dist/spa/index.html:39` |

`dist/` é evidência do build local disponível, não do que está servido em produção. O worker fonte já limita o fallback de navegação a `/motoboy`, mas isso não limita o escopo do registro nem a associação global do manifesto. `MotoboyInstallButton` só foi encontrado em `Motoboy.tsx`; ocultar esse componente não resolve a configuração global.

## 2. Agente Responsável

Orquestrador: coordenação, classificação como auditoria/planejamento, dependências, critérios e consolidação. Arquiteto será responsável pelo fechamento técnico dos contratos estruturais antes da implementação correspondente.

## 3. Agentes Envolvidos

Nesta auditoria participaram três agentes de apoio: KDS/entregas; estoque/impressão; pedidos/pagamentos. O Orquestrador revisou visitantes/PWA, estrutura, documentação, baseline de testes e integração do plano.

Na execução: Product Owner fecha regras e aceite; Arquiteto valida contratos e infraestrutura de impressão/eventos; Database cuida das migrations; Backend implementa regras e transações; Frontend integra via API canônica; QA-DevOps valida cada incremento e a operação real. Não executar fases independentes sobre os mesmos writers de estoque/pedido sem coordenação.

## 4. Plano de Execução

### 4.1 Regras que orientam todos os incrementos

1. Um catálogo e um motor de preços. Modal desktop e página mobile usam o mesmo composer, orçamento e serviço autenticado de criação.
2. `OrderService` e a máquina vigente continuam autoridades comerciais. Etapas de montagem, forno, conferência e embalagem não redefinem silenciosamente `ready_for_pickup`.
3. Pagamento operacional não é inferido pelo KDS Expedição. A forma e a situação são definidas no atendimento/checkout; a confirmação da cobrança na entrega pertence ao motoboy. A Expedição não consulta, altera ou presume pagamento.
4. Uma transformação física e uma baixa por identidade de negócio. O clique do pizzaiolo inicia uma contagem de cinco segundos; somente ao final o servidor bloqueia e reserva/consome o estoque. Retry reaproveita resultado; refazimento real tem nova tentativa, motivo e consumo próprio conforme regra aprovada.
5. Reimpressão consulta snapshot imutável e cria auditoria de impressão, sem movimentar estoque.
6. A entrada de estoque confirma, por produto ou exceção de lote, se há porcionamento obrigatório. Somente produtos marcados como porcionáveis geram tarefa automática no KDS Cozinha Preparo.
7. Backend valida tenant, permissão, estado, versão e capacidade. Proteção de rota React não substitui autorização.
8. Nenhum transporte externo participa mantendo locks de estoque abertos: evento/job durável é persistido com a operação; envio ocorre depois do commit.
9. Comandos expõem falhas e conflitos. Reconexão reconcilia estado; não dispara indiscriminadamente nova mutação.
10. Evoluções de contratos são aditivas/compatíveis. Mudança incompatível exige versão, sem troca silenciosa de envelope ou tipos decimais publicados.

### 4.2 Fluxo operacional proposto

```text
Planejamento aprovado -> ordem de preparo -> execução e transformação atômica
  -> lote de preparado disponível -> etiquetas de preparo

Upload/foto de nota ou cupom, ou entrada manual -> conferência
  -> entrada de compra confirmada -> decisão “porcionar?”
  -> tarefa automática no KDS Cozinha Preparo, quando aplicável
  -> porcionamento transacional -> lote preparado -> etiqueta

Pedido comercial elegível -> unidades físicas -> tentativas de montagem
  -> clique do pizzaiolo -> contagem regressiva de 5 segundos
  -> bloqueio/reserva atômica de insumos no servidor
  -> estoque disponível: iniciar preparo
  -> estoque indisponível: exceção para atendimento/gerência
  -> todas as montagens concluídas -> Finalizar montagem
  -> entrada automática na Expedição, com estado de forno visível
  -> assamento confirmado quando necessário -> embalagem por unidade
  -> bebidas/adicionais/quantidades/lacres conferidos -> Finalizar Expedição
  -> pedido efetivamente pronto
      -> entrega própria: fila -> reserva -> coleta real -> entrega -> retorno
      -> entrega externa: fluxo da plataforma, sem reservar motoboy próprio
      -> retirada: liberação e coleta no balcão
      -> salão: fluxo da comanda existente
```

O pedido chega à visão da Expedição após a montagem completa, mas isso não significa que já saiu do forno. Cada unidade tem etapa de assamento explícita; embalagem e liberação final permanecem bloqueadas quando uma etapa obrigatória não foi confirmada. Pedidos só com bebidas/outros produtos seguem classificação própria, sem forno fictício. A Expedição não recebe nem altera dados de pagamento; essa informação permanece no atendimento/checkout e, quando necessário, no fluxo do motoboy.

### 4.3 Etapas priorizadas e gates de entrega

| Etapa | Prioridade / dependência | Entrega e responsável | Gate verificável |
| --- | --- | --- | --- |
| E0 — Baseline e definições | Bloqueante | PO/Arquiteto/QA: conciliar contratos atuais, regras físicas e escritores; registrar escopo e decisões | Matriz de estados/atores, regime de consumo, combinações e política de pagamento aprovados; baseline reproduzível |
| E1 — Confiabilidade imediata | P0; após E0 aplicável | Backend/Frontend: corrigir rotas/DTOs, bloquear dupla baixa, implementar contagem de 5 s e exceção de insumo; retirar pagamento da Expedição | Testes HTTP e PostgreSQL comprovam que o primeiro bloqueio vence, o segundo recebe exceção, nenhum consumo se duplica e a Expedição não interpreta pagamento |
| E2 — Visitantes e PWA | P0; independente de estoque | Backend/Frontend/QA: presença pública e isolamento da instalação Motoboy | Admin/KDS/motoboy/TV/404 não contam; abas públicas deduplicam; sem oferta Motoboy fora da rota |
| E3 — Venda manual compartilhada | P1; E0/E1 | Backend/Frontend: busca/cadastro rápido, orçamento e criação autenticados; modal e página touch | Desktop e mobile criam o mesmo pedido uma vez, com preço, cliente, modalidade e permissão corretos |
| E4 — Comprovante operacional | P1; contrato financeiro E1 | Frontend/Backend: evoluir modelos existentes, logo tenant, bebidas, pagamento e checklist | Prévia/teste legíveis na bobina; 74,99/100,00 resulta em troco 25,01; origem real preservada |
| E5 — Impressão física | P1; inventário hardware E0 | Arquiteto/Backend/QA: agente local dentro da LAN, fila e evolução do cadastro/templates existentes | Agente autenticado identifica a impressora configurada, imprime no equipamento correto, informa falhas e distingue timeout de resultado desconhecido |
| E6 — Entrada, preparo e porcionamento | P1; E1 e regime de estoque | Backend/Database/Frontend: decisão de porcionamento na conferência da entrada, tarefa automática, receita, transformação, lote e validade | Produto não porcionável não gera tarefa; produto porcionável gera tarefa; 40 porções de 150 g consomem 6 kg e entram 40 porções; rollback/retry/concorrência comprovados |
| E7 — Etiquetas de preparo | P1; E5/E6 para hardware | Backend/Frontend: origem execução/lote, validade, responsável e reimpressão autorizada | Etiqueta correta na cozinha; reimpressão não altera um único movimento |
| E8 — Pizzaiolo e forno | P1; E1 e regime exclusivo de consumo | Backend/Frontend: unidades automáticas, ficha congelada, contagem de 5 s, reserva de estoque, fila de exceções, timers, presença e atribuição | Duas pizzas iguais têm IDs distintos; o primeiro bloqueio vence; o segundo recebe exceção com retorno ao atendimento; forno não é presumido |
| E9 — Expedição individual | P1; E8, E4 e integração E5 | Backend/Frontend: embalagem e checklist persistidos; conclusão agregada; projeção sem pagamento | Itens pendentes bloqueiam conclusão; caixas 1/N corretas; Expedição não altera nem presume pagamento; retirada e frota externa seguem seus fluxos |
| E10 — Motoboys e fila automática | P1; evento de conclusão E9 | Backend/Database/Frontend: reserva, retorno, fila, timeout e reatribuição | Disputas concorrentes não duplicam reserva; frota externa excluída; coleta explícita antes de em entrega |
| E11 — PCP e indicadores | P2; E6/E8/E9/E10 | Backend/Frontend: previsão semanal revisável, sugestões e métricas auditáveis | Demanda não duplicada; gestor aprova tarefas; indicadores reproduzíveis pelos eventos/timestamps |
| E12 — Homologação e implantação | Por incremento e gate final | QA-DevOps/Orquestrador: PostgreSQL, dispositivos, LAN, hardware, release controlada | Todos os aceites rastreados; migração e operação real evidenciadas; pendências expostas |

E2 pode avançar sem aguardar o restante do domínio operacional. E4 pode ser entregue antes do conector físico pela impressão atual do navegador. E6 permite homologação transacional antes da impressão real, mas seu aceite integral com etiquetas depende de E5/E7. E11 não bloqueia as correções prioritárias nem substitui programação manual de preparos.

Eventos recuperáveis pertencem explicitamente a E8/E9/E10: finalizar montagem, concluir expedição ou alterar disponibilidade deve atualizar o outro posto sem refresh manual. O gate inclui reconexão, eventos repetidos e recuperação do snapshot; polling isolado de 10–15 segundos não satisfaz esse aceite.

### 4.4 Estados fechados para a execução

| Estado | Entrada | Saída permitida |
| --- | --- | --- |
| `aguardando_inicio` | Pizzaiolo clica para iniciar | inicia contagem de 5 segundos |
| `contagem_em_andamento` | Timer ativo no cliente | servidor recebe confirmação; cancelamento mantém a unidade pendente |
| `aguardando_reserva` | Cinco segundos concluídos | transação tenta bloquear insumos pela ordem do timestamp confirmado pelo servidor |
| `preparo_iniciado` | Reserva/consumo concluído | segue montagem, forno e conferência |
| `aguardando_analise` | Reserva recusada por falta de insumo | atendimento/gerência decide compra, contato, substituição ou cancelamento autorizado |
| `retorno_atendimento` | Ação explícita da gerência/atendimento | pedido preservado com alerta, histórico e nova decisão operacional |

O timer é apenas uma janela operacional. A ordem da disputa usa o timestamp recebido pelo servidor e a transação com lock no PostgreSQL; o relógio do navegador nunca decide o vencedor.

### 4.5 Contratos dos quatro ambientes

| Ambiente | URL de tela | Escopo do contrato |
| --- | --- | --- |
| KDS Cozinha Preparo | `/painel/preparo` | Entradas porcionáveis, tarefas, ficha, quantidade produzida, gramatura, lote, validade, responsável e etiquetas |
| KDS Pizzaiolo | `/painel/cozinha` | Unidades/pizzas, composição, timer, reserva de insumos, montagem, forno e exceções de estoque |
| KDS Expedição | `/painel/expedicao` | Pizzas, bebidas, adicionais, embalagens, lacres, checklist e liberação; sem pagamento |
| TV Motoboys | `/tv/motoboys` | Fila, reserva, coleta, entrega, retorno e disponibilidade da frota própria |

As rotas não devem compartilhar um DTO operacional genérico. O backend manterá `/api/preparation/...`, `/api/kds/kitchen/...`, `/api/kds/dispatch/...` e `/api/order-board/...`, com RBAC e payloads específicos por ambiente.

### 4.6 Especificação executável por frente

**Venda manual desktop/mobile.** Manter `/painel/orders` como Operações e acrescentar “Fazer Pedido”. Rota mobile proposta: `/painel/orders/novo`, sujeita ao registro explícito no AdminGuard/navegação. O modal e a página usam componente controlado compartilhado, com rascunho independente do carrinho público. Fluxo: cliente → modalidade → catálogo/configuração → carrinho → endereço/frete → pagamento → revisão → confirmação. Reaproveitar configurador de `Product.tsx` após extrair seus vínculos com a loja pública. Back-end revalida tudo, inclusive preços por canal, limites de sabores, opções, estoque e taxa. Consumo local delega ao domínio de mesas/comandas. Confirmação recebe chave estável de idempotência; refresh/retry consulta o resultado da mesma operação. Cliente rápido usa identidade real por telefone e contrato administrativo, sem fabricar e-mail. Pagamento já recebido exige ação autorizada/auditável; pago online exige evidência confiável do provedor.

**Financeiro, bebidas e comprovantes.** Criar uma projeção operacional compartilhada com origem, modalidade, itens/componentes, bebidas, método, situação, provedor/proveniência, valor a cobrar, valor entregue e troco. Detectar bebida por categoria/tipo/composição estruturada, nunca por nome. Não foi localizada composição comercial completa de combos no escopo revisado: verificar dados reais e normalizar snapshot de componentes somente onde necessário, sem duplicar preços nem consumo. Mostrar pendente/desconhecido quando faltar evidência; “PAGO ONLINE — NÃO COBRAR” somente quando confirmado. Mostrar pagamento também na retirada. Comprovante reutiliza identidade tenant e modelos existentes; logo proporcional, centralizado e convertido para saída monocromática conforme transporte. Fundo cinza na UI/saída compatível; em térmica, título forte, linhas e contraste garantem destaque mesmo sem fundo. Carregar logo antes de imprimir; fallback mantém nome correto. Preservar integralmente emissão fiscal.

No KDS Expedição, a projeção financeira não será exposta. O comprovante comercial, o atendimento e o fluxo do motoboy poderão usar o contrato financeiro autorizado, mas a Expedição receberá somente os dados necessários à conferência física.

**Impressoras.** Evoluir `LabelSettingsPanel`, `LabelService` e tabelas existentes com setor/finalidade preparo e comprovante, vínculo de várias impressoras por ambiente, tamanho, protocolo, modo manual/automático e preferência de roteamento. A escolha final do conector depende do equipamento e da rede: serviço local próximo às impressoras, autenticado e vinculado ao tenant, comunica-se com a fila existente/evoluída; navegador e VPS não presumem acesso TCP à LAN. A execução terá quatro gates: registrar o agente no tenant; testar conectividade da LAN; cadastrar/validar IP, porta e protocolo da impressora; vincular impressora ao ambiente e executar impressão de teste. Preferir comunicação de saída do agente local, sem expor impressoras à internet. Registrar solicitado, aceito/enviado, erro e resultado desconhecido; confirmação física somente quando o protocolo a fornecer. Timeout após envio não autoriza reimpressão cega. Configurar teste e diagnóstico pelo mesmo transporte real. Manter `dialog_opened` como evidência de diálogo do navegador, sem renomeá-la para impresso. Retenção de dados pessoais dos jobs e credenciais do conector devem ter acesso restrito.

**Preparo.** Corrigir rotas sombreadas e schemas antes de habilitar a interface. Reutilizar receitas operacionais e ordens existentes, expondo nome, programação, unidade, rendimento, produzido/restante, instruções, responsável, início, pausas e conclusão. Ponto de entrada proposto `/painel/preparo`, com autorização específica que não amplie indevidamente contas de cozinha ou estoque. A entrada poderá vir de upload/foto de nota ou cupom, ou de digitação manual; OCR é opcional, mas conferência e confirmação manual são obrigatórias. Na conferência da entrada, o responsável marca cada produto como `porcionável` ou `não porcionável`; essa decisão fica registrada no produto/ficha e pode ter exceção auditada por lote. A confirmação de uma entrada porcionável cria automaticamente uma tarefa no KDS Cozinha Preparo. Cada apontamento aprovado gera uma operação física durável: bloquear ordem/lotes; revalidar versão, validade e saldo; consumir bruto proporcionalmente; registrar entrada do produto preparado no estoque e criar/vincular o lote; vincular genealogia, perdas/rendimento, responsável e execução; persistir resultado idempotente e evento; commit único. `complete` fecha a ordem sem repetir movimentos já registrados nos apontamentos. Validade deriva de regra aprovada por receita/categoria e das restrições de insumos, nunca de prazo inventado. Preparados são consumidos como preparados na venda, sem nova baixa do bruto. Etiqueta é comando separado sobre execução/lote congelados; impressão falha não desfaz preparo físico realizado.

**Pizzaiolo, forno e expedição.** Preservar `/painel/cozinha`, mudando o nome visível para KDS Pizzaiolo. Criar unidades físicas para quantidade comercial e manter uma pizza de três sabores como uma unidade. Inicializar de forma idempotente no marco comercial autoritativo, incluindo salão e outros canais elegíveis. Modal técnico usa composição congelada, sem custos/estoque administrativo exposto ao posto. Temporizador deriva de timestamps do servidor. Validar dono da tarefa, pedido elegível, estado e versão. Presença expira por heartbeat e não equivale a login. Distribuir inicialmente por disponibilidade/carga, com divisão entre operadores configurável; usar estimativas apenas quando baseadas em dados. Concluir montagem de uma unidade não conclui o pedido. Agregador servidor habilita Finalizar montagem após todas as unidades exigidas. Expedição mantém estados por unidade/embalagem e checklist versionado, com autor/data; conclusão exige forno e todos os itens obrigatórios. Etiquetas reutilizam as identidades físicas e a contagem de volumes existentes.

**Consumo e refazimento.** Persistir o regime de execução/consumo do pedido e sua cobertura, em vez de inferi-lo só da flag atual ou da tela. Pedidos já consumidos no legado não consomem novamente na primeira tentativa. Novos pedidos do regime unitário têm um único marco físico de consumo aprovado ao final da contagem de cinco segundos; manter compatibilidade com pedidos legados em andamento. Conciliar snapshots CMV, ingredientes efetivos, movimento e tentativa. Refazimento cria nova tentativa e registra perda/novo consumo segundo a regra; retry não cria tentativa. Quando a reserva falhar, a unidade entra em `aguardando_analise`, gera alerta para atendimento/gerência e oferece **Voltar para Atendimento**; não cancela nem apaga o pedido automaticamente. Não desligar/ligar writers incompatíveis sobre pedidos ativos como mecanismo de rollback.

**Motoboys.** Consolidar caminhos de atribuição no serviço autoritativo, aproveitando locks do KDS e preservando contratos existentes. Separar operacionalmente offline, disponível, reservado, em entrega, retornando e indisponível, com histórico. Entrega concluída não significa disponível fisicamente na pizzaria. Autoatribuir somente pedido concluído na expedição, de entrega própria e elegível, conforme configuração. FIFO por conclusão de expedição como padrão; prioridade por prazo/atraso configurável e auditada. Motoboy retornando pode receber reserva se permitido, sem simular coleta. Usar ETA/localização só com dados autorizados e confiáveis; fallback por disponibilidade, carga e horários reais. Reserva atômica trava pedido e capacidade; recusa, indisponibilidade e prazo liberam/reorganizam reserva com motivo. Gatilhos obrigatórios: conclusão da Expedição, mudança para retornando, confirmação de retorno físico, recusa, timeout e indisponibilidade. Acionar por evento durável e rotina de recuperação. Coleta registra instante real e só então avança entrega; conclusão e retorno são ações distintas. Integrações de frota externa permanecem fora da fila própria.

**Visitantes públicos.** Reutilizar identidade e domínio de sessões/eventos existentes, adicionando presença por sessão/aba se os campos atuais não representarem esse ciclo. Classificar positivamente rotas de vendas no frontend e backend; incluir aliases públicos reais como `/menu`; excluir painéis, KDS, motoboy, TV, erros e demais ambientes. Administrador na loja conta nessa navegação, sem filtro pelo papel do usuário. Heartbeat somente enquanto a loja estiver ativa, com um único TTL configurado e usado por Marketing, BI e tráfego; entrada/saída e mudança para ambiente interno atualizam a presença da aba. O fechamento de uma aba não encerra outra aba pública válida. Deduplicação por tenant + identidade de navegador/sessão; não por IP, para não agrupar clientes distintos. Evento de saída é tentativa de melhor esforço; TTL garante expiração em queda de rede/encerramento abrupto. Centralizar a consulta de presença, sem apagar histórico de analytics. Contagem tem latência limitada por heartbeat/TTL, não precisão instantânea impossível em desconexões abruptas.

**Instalação PWA.** Remover injeção automática global do manifesto/registro e os metadados Motoboy do HTML compartilhado; associá-los somente à superfície Motoboy. Usar escopo e URL canônicos do aplicativo, preservando entrada antiga com compatibilidade explícita e validando a diferença entre `/motoboy` e subrotas. Isolar worker, cache, fallback e metadados; migrar o worker antigo registrado em `/`, invalidar caches incompatíveis de forma controlada e validar instalações existentes antes de remover qualquer registro. Planejar atualização das inscrições push sem perder suporte ao aplicativo já instalado. A fonte atual do worker não comprova uma integração push completa; identificar consumidores e inscrições reais antes da migração. Escutar `beforeinstallprompt` somente no Motoboy e limpar eventos ao sair. Android/desktop: validar instalação quando elegível; iOS: orientação manual somente no ambiente correto, respeitando suporte da plataforma. Verificar acesso direto, navegação SPA e primeira visita antes do React hidratar; esconder o botão não satisfaz o aceite.

**Impressão em rede.** A escolha de IP não será executada diretamente pelo navegador ou pelo VPS. O plano adota um agente local instalado na LAN da pizzaria. O agente autentica-se no tenant, consulta uma fila durável e comunica-se com a impressora pelo protocolo homologado para o modelo real (IPP/CUPS, ESC/POS, TSPL, ZPL ou equivalente). O cadastro continuará armazenando IP/hostname, porta, protocolo, setor, mídia e finalidade. Descoberta por mDNS/SNMP será auxiliar, nunca requisito. O agente deverá reportar conectado, enviado, erro e resultado desconhecido; timeout após envio não dispara reimpressão automática.

**Eventos e planejamento.** O polling atual permanece como reconciliação. Reutilizar infraestrutura de eventos persistentes onde suportar entrega independente por consumidor; bus em memória não garante recuperação entre processos. Definir transporte KDS autenticado e isolado por tenant (stream ou equivalente compatível) com reconexão e consulta do snapshot, sem instalar um segundo broker por conveniência. PCP calcula demanda por dia da semana, receitas/rendimento, estoque utilizável, reservas, validade, tarefas abertas e capacidade. Exibir origem e qualidade da previsão; sugerir revisão aprovada pelo gestor, sem criar produção duplicada ou inventar demanda. Indicadores derivam de tempos persistidos por tarefa/unidade/embalagem/reserva/coleta/entrega/retorno, diferenciando medição real de estimativa.

### 4.7 Módulos, arquivos e dados afetados

| Domínio | Arquivos principais | Dados a reutilizar/evoluir |
| --- | --- | --- |
| Rotas/identidade | `client/App.tsx`, `client/components/AdminGuard.tsx`, `client/config/adminNavigation.ts`, `backend/core/rbac_authorization.py`, contexto tenant e barreiras de estação | Usuários, papéis, permissões e configuração tenant existentes |
| Pedido manual | `Orders.tsx`, `Product.tsx`, `AdminSalao.tsx`, novos componentes controlados de atendimento; `routes/orders.py`, `schemas/order.py`, `services/order_service.py`, clientes/identidade | `orders`, `order_items`, `order_item_flavors`, `payments`, `customers`, endereços, produtos/opções, mesas/comandas |
| Pagamento/conferência | `Expedicao.tsx`, `kds_service.py`, schemas KDS/pagamento, `printing.ts` | Método/situação/proveniência; snapshot de componentes quando necessário; troco derivado do total final |
| Produção | `Cozinha.tsx`, `KdsMultiOperatorBoard.tsx`, `routes/kds.py`, `schemas/kds_production.py`, `kds_production_service.py`, `kds_service.py`, `order_service.py` | `production_units`, `production_attempts`, `production_attempt_consumptions`, `kds_operator_states`, `kds_assignments` |
| Preparo/estoque | `PreparationOperationsPanel.tsx`, `GestaoInventory.tsx`, `routes/preparation.py`, `schemas/preparation.py`, `preparation_service.py`, `inventory_foundation_service.py`, `inventory_service.py`, resolução de receitas e CMV | `inventory_operation_recipes/items`, `preparation_orders/executions`, `inventory_operations`, movimentos, lotes, reservas, genealogia e snapshots |
| Impressão | `AdminConfiguracoes.tsx`, `LabelSettingsPanel.tsx`, `LabelPrintDialog.tsx`, `printing.ts`, `labelPrinting.ts`, `routes/labels.py`, `schemas/label.py`, `label_service.py`; futuro conector local | `label_printers`, `label_templates`, `label_printer_templates`, `label_settings`, `label_volume_rules`, `label_versions`, `label_volumes`, `label_print_jobs` |
| Entrega | `delivery_service.py`, `routes/delivery.py`, `models/delivery.py`, `Motoboy.tsx`, logística e Expedição | `Delivery`, `DeliveryPerson`, eventos e configurações logísticas; reserva/retorno/capacidade auditáveis |
| Visitantes | `tracking.ts`, `TrackingInjector` em `App.tsx`, `routes/marketing.py`, `paid_traffic_service.py`, `business_intelligence_service.py` | `visitor_profiles`, `visitor_sessions`, `visitor_events`, configuração Marketing; presença/abas conforme contrato final |
| PWA | `vite.config.ts`, `index.html`, `client/sw.ts`, `MotoboyInstallButton.tsx`, `site_config_service.py`, `routes/site_config.py`, `server/node-build.ts`, cache/reverse proxy quando aplicável | Manifesto por ambiente, registro e migração de worker/cache/inscrições existentes |

Todos os clientes de API passam por `client/lib/api.ts`; os nomes de novos arquivos/entidades são fechados no desenho da etapa. Não criar tabelas duplicadas apenas porque estão listadas como possibilidade no plano.

**Migrations prováveis:** idempotência/origem da venda manual, regime/cobertura de consumo, restrições de preparo, timestamps/pausas faltantes, vínculo execução/operação/lote, conferência/embalagem, conclusão de expedição, estados/reservas de entrega, origem preparo nos templates/jobs, transporte de impressão e presença por aba se necessária. Cada alteração exige verificação do schema aplicado, backfill seguro, FKs tenant-safe, unicidades e índices de fila/expiração. Reutilizar registro genérico de idempotência onde seu contrato servir. Não editar migrations históricas nem preencher lotes/validade históricos inventados.

Migrations existentes relevantes: `20260926_dispatch_labels`, `20261020_product_order_options`, `20261020_inventory_recipe_fractions`, `20261021_inventory_foundation`, `20261021_inventory_recipe_details`, `20261022_inventory_traceability`, `20261022_preparation_execution`, `20261022_kds_production`, `20261022_kds_attempt_consumption`. Próximas migrations devem partir do head real no momento da execução, não do último arquivo desta lista temática.

### 4.8 Estratégia de testes e critérios de aceite

| Grupo | Cenários obrigatórios / resultado |
| --- | --- |
| Venda | Pedido completo no modal e celular/tablet; cliente novo/existente; entrega/retirada/salão; até três sabores; bebidas/variantes/adicionais; orçamento recalculado no servidor; falha/retry cria um pedido |
| Permissões | Funcionário sem escrita bloqueado por HTTP; cliente/item/impressora/lote de outro tenant rejeitados; ficha operacional não vaza custos; nova rota reconhecida no guard |
| Pagamento | Atendimento/checkout define forma e situação; motoboy confirma cobrança quando aplicável; Expedição não recebe nem altera pagamento; 100,00 − 74,99 = 25,01; valor insuficiente rejeitado; nenhuma suposição de quitação |
| Produção | Uma pizza, três diferentes, duas iguais, dois pizzaiolos no mesmo pedido, clique simultâneo, contagem de 5 s, primeiro bloqueio vence, segundo entra em exceção, retorno para atendimento, conclusão parcial, refresh/fechar modal/reconexão, forno obrigatório/opcional |
| Expedição | Uma confirmação por embalagem; progresso 1/N; bloqueio com item pendente; bebidas inclusive composição real; adicionais/quantidades/lacres; retirada e frota externa sem motoboy próprio |
| Consumo | Pedido legado não baixa novamente; tentativa nova baixa uma vez ao fim da contagem; tentativa sem saldo não baixa; refazimento novo consumo; receitas/frações/CMV coerentes; cancelamento não devolve insumo usado indevidamente |
| Entrada e preparo | Produto marcado não porcionável não cria tarefa; produto porcionável gera tarefa após entrada confirmada; 40 × 150 g consome 6 kg e entra 40 porções; lote/validade/responsável presentes |
| Porcionamento | 40 × 150 g = saída 6 kg/entrada 40; lote e responsável; unidades compatíveis; validade/FEFO; perda/rendimento; lotes bloqueados/vencidos; falha intermediária faz rollback integral |
| Concorrência PostgreSQL | Duas sessões independentes disputando criação, unidade, apontamento, estoque e motoboy; mesma chave/conteúdo retorna resultado; conteúdo divergente conflita; sem saldo/reserva duplicados |
| Etiquetas/impressão | Caixas 1/N; origem lote; logo correto por tenant; modelos/tamanhos; equipamento correto; offline, timeout após envio, resultado desconhecido, reimpressão autorizada sem estoque |
| Entregas | Conclusão da Expedição dispara fila; disponível; todos ocupados; um/dois retornando; dois pedidos simultâneos; recusa/pausa/timeout; capacidade; reatribuição; coleta efetiva; conclusão separada do retorno; fallback sem GPS |
| Visitantes | Admin/KDS/motoboy/TV/404 não contam; loja conta inclusive admin como cliente; duas abas contam uma identidade; fechar uma mantém outra; saída/rede/TTL expiram; indicadores concordam |
| PWA | Android/iOS/desktop; acesso direto e SPA; cliente nunca recebe app Motoboy; instalação elegível só na rota; worker antigo/cache atualizado; aplicativo já instalado continua utilizável |
| Planejamento/métricas | Média semanal configurada, sem histórico, ajustes do gestor, tarefas abertas e demanda sem duplicação; tempos calculados pelos registros reais |
| Regressão | Loja → checkout → pagamento → KDS → estoque → CMV/BI; salão; WhatsApp quando afetado; fiscal preservado; integrações efetivamente instaladas mantidas |

O grupo produção/expedição/entregas cobre os 24 cenários do anexo, incluindo indisponibilidade após atribuição, concorrência entre dispositivos e rede durante temporizador. Não substituir testes de integração por verificações textuais de que um método existe.

**Baseline executado nesta análise:**

- `python -m alembic -c backend/alembic.ini heads`: um head, `20261022_receipt_pdf_camera_evidence`.
- `python -m pytest tests/test_kds_production_phase7.py tests/test_dispatch_labels.py tests/test_operational_delivery_safety.py tests/test_wave6_marketing_tenant.py -q -p no:cacheprovider --basetemp=.runtime/pytest-gran-torino-plan-20261026`: **23 aprovados**, cinco avisos de depreciação/mapeamento ORM.
- `npm.cmd test -- client/lib/kds.spec.ts client/lib/labelPrinting.spec.ts client/lib/printing.spec.ts`: **13 aprovados**, três arquivos.
- O Python da `.venv` do backend não tinha pytest; a seleção foi executada com Python 3.12 disponível no ambiente, sem instalar dependências ou modificar a venv.
- Parte da seleção backend inspeciona código; etiquetas incluem cenário com SQLite. Esses resultados não comprovam concorrência PostgreSQL nem aceites completos dos três prompts.
- Não foram executados nesta etapa: suíte completa, build novo, migration aplicada, integração HTTP autenticada ponta a ponta, browser em dispositivos, entrega em plataforma ou impressão física.

## 5. Dependências

### 5.1 Definições operacionais antes da fase correspondente

| Decisão | Proposta segura para fechamento | Etapas afetadas |
| --- | --- | --- |
| Marco físico de consumo | Clique do pizzaiolo inicia contagem de 5 s; no término, o servidor bloqueia, ordena a disputa e reserva/consome uma única vez. Pedidos legados permanecem cobertos por regime compatível | E1/E8 |
| Falha de estoque | Unidade fica `aguardando_analise`, gera alerta e oferece **Voltar para Atendimento**; não cancelar automaticamente | E1/E8 |
| Responsabilidade financeira | Atendimento/checkout define forma e situação; motoboy confirma cobrança na entrega; Expedição não recebe nem altera pagamento | E1/E3/E9/E10 |
| Atendimento com loja pública fechada | Preservar restrição vigente até existir permissão/regra explícita; sem bypass silencioso | E3 |
| Consumo no local | Vincular mesa/comanda conforme operação atual; confirmar atendimento sem mesa antes de expandir | E3 |
| Composição dos combos | Confirmar cadastros reais e componentes; não supor que promoções equivalem a combos estruturados | E1/E3/E4/E9 |
| Receitas, rendimento e validade | Parâmetros fornecidos/aprovados pela operação, incluindo pausas, perdas e unidades | E6/E7/E11 |
| Responsabilidade pelo forno | Confirmar quem inicia/retira/confere; manter estados separados da montagem | E8/E9 |
| Entregadores retornando | Reserva configurável; capacidade e prazo definidos; coleta continua explícita | E10 |
| Impressoras/rede | Modelo, protocolo, mídia, DPI, IP/porta, local do agente na LAN, credencial de registro e acesso ao equipamento | E5/E7 |
| Porcionamento | Decisão obrigatória na conferência da entrada: produto porcionável gera tarefa automática; produto não porcionável segue ao estoque disponível | E6/E7 |
| Presença pública | Fechar política de aba visível/ativa e TTL comum; cinco minutos é apenas referência do comportamento atual | E2 |

Essas decisões não impedem executar correções independentes após aprovação do plano. São gates da funcionalidade correspondente, sem criar bloqueio geral artificial.

### 5.2 Recursos de validação

Banco PostgreSQL descartável para migrations/concorrência; cadastros representativos de produtos, receitas e preparados; usuários de cada posto; duas empresas para isolamento; equipamentos reais com bobinas/etiquetas; celulares Android/iOS e tablet; credenciais de homologação dos provedores quando necessário. Para iFood/99Food/Keeta, confirmar quais adapters estão de fato instalados e disponíveis. Contratos locais não versionados não equivalem a integração homologada.

### 5.3 Limites de escopo

O plano cobre integralmente os três prompts. Não inclui reescrever arquitetura, criar outro fiscal/gateway, substituir catálogo ou fabricar conectores de marketplace sem contrato/credenciais. Pagamento misto só entra como evolução adicional se a regra e o modelo forem aprovados; a condição “caso suportado” hoje não se verifica. OCR/recebimento fiscal e reestruturação geral de ERP não são novas entregas deste plano; entram apenas na regressão de dependências afetadas.

## 6. Controles obrigatórios de segurança e integridade

Os itens abaixo não são riscos aceitáveis do produto. São condições obrigatórias de implementação. Se qualquer controle falhar, a etapa não passa no gate e não pode ser liberada.

| Controle obrigatório | Garantia exigida | Bloqueio de liberação |
| --- | --- | --- |
| Isolamento multitenant | Toda leitura, escrita, job, cache, arquivo, política e impressão recebe tenant do contexto autenticado no servidor; FKs, filtros e testes impedem acesso cruzado | Qualquer teste cross-tenant com sucesso interrompe a entrega |
| Publicação LGPD | Criar, editar ou gerar modelo sempre cria rascunho; somente ação explícita de gestor autorizado publica uma versão; auditoria registra ator, tenant e versão | Não existe caminho automático de publicação |
| Clientes importados | Telefone normalizado é a regra primária de identidade e duplicidade dentro do tenant; registros existentes não são sobrescritos sem confirmação autorizada; e-mail é verificação complementar | Arquivo com telefone já cadastrado é associado ou relatado, nunca duplicado silenciosamente |
| Consentimento promocional | Importação e cadastro não concedem consentimento por inferência; consentimento só muda por ação explícita autorizada e auditável do gestor ou cliente | Qualquer consentimento criado implicitamente reprova a etapa |
| Métricas Marketing/CRM | Indicadores derivam de consultas e eventos persistidos; schemas validam respostas; vazio é estado válido; falha externa aparece como indisponibilidade, sem números substitutos | Métrica sem origem rastreável ou divergente do banco bloqueia a liberação |
| Rotas e permissões | Reordenação de abas preserva URLs, aliases, deep links e RBAC; cada endpoint repete a autorização no backend | Link direto, usuário autorizado ou não autorizado com comportamento incorreto reprova a etapa |
| Fórmulas financeiras | Fórmulas e classificações existentes ficam fora da alteração; qualquer mudança exige evidência, revisão do Arquiteto/Database e testes de reconciliação | Diferença financeira sem justificativa impede migration e release |
| Regressão compartilhada | Contratos de APIs, componentes e módulos compartilhados têm testes de contrato e regressão antes e depois da alteração | Qualquer falha em KDS, pedidos, catálogo, BI, loja ou integrações impede conclusão |
| Estoque e concorrência | Writer único, transação PostgreSQL, idempotência e constraints impedem baixa duplicada, pedido incompleto e reserva duplicada | Concorrência sem resultado determinístico bloqueia a entrega |
| Impressão e PWA | Agente, manifesto, worker e filas respeitam tenant e ambiente; timeout não vira sucesso e PWA Motoboy não aparece fora da rota | Falso sucesso, vazamento ou oferta fora do ambiente reprova |

O quadro histórico abaixo passa a ser tratado apenas como matriz de controles e verificações de implementação. Ele não representa riscos aceitos: cada linha exige teste, evidência e bloqueio de release quando falhar.

| Risco | Mitigação e condição de liberação |
| --- | --- |
| Baixa duplicada entre legado e tentativas | Regime persistido, ponte de cobertura, writer único, conciliação e concorrência PostgreSQL antes de E8 |
| Pedido incompleto/sem assamento liberado | Gates no servidor, agregação de unidades e conclusão de expedição independente |
| Cobrança incorreta ao cliente | Situação/proveniência financeira real, sem inferir pelo método/status comercial; pendente/desconhecido explícito |
| Duplicação por rede ou toque | Identidade de negócio durável, payload hash, constraints, locking e resultado de replay |
| Impressão repetida ou falsa confirmação | Estados compatíveis com o transporte, resultado desconhecido, auditoria e reimpressão deliberada |
| Estoque preparado sem origem/custo | Transformação e genealogia atômicas, unidades/rendimento/validade validados e CMV reconciliável |
| Motoboy duplicado ou frota errada | Elegibilidade, capacidade e reserva transacionais; excluir logística externa |
| Regressão em pedidos já ativos | Corte por regime, backfill verificado e compatibilidade com leitores/escritores legados |
| Vazamento entre empresas/postos | Contexto tenant no servidor, FKs consistentes, RBAC por ação, DTO técnico sem custos e isolamento de conector/jobs |
| Persistência antiga de PWA | Migração testada do worker/caches e dos aplicativos existentes, com validação em HTTPS |
| Contador ainda medir eventos em vez de presença | Serviço comum de presença, ciclos por aba, TTL e testes de saída/conexão; preservar analytics separado |
| Confundir docs/testes estáticos com conclusão | Aceites rastreados por comportamento HTTP, banco real, dispositivo e equipamento, com limites explícitos |

**Implantação:** mudanças expansivas via Alembic; ensaio em banco descartável e cópia representativa quando autorizada; build obrigatório; release imutável com SHA validado; health e fluxos autenticados; ativação gradual por estabelecimento. Verificar logs antes de restart em falhas. Não executar deploy nesta etapa documental. Recuperação de código não apaga movimentos/auditoria e não reativa writer incompatível com o regime persistido. Confirmar o runbook versionado atual, pois documentação histórica de serviços/paths pode estar defasada.

### 6.1 Eliminação das causas na origem

A segurança não será obtida aceitando riscos e interrompendo a entrega depois que eles aparecerem. Cada causa conhecida será eliminada no desenho do dado, no serviço, na API e na interface. Os requisitos abaixo são invariantes permanentes do sistema:

| Problema que não pode existir | Causa técnica eliminada | Implementação obrigatória |
| --- | --- | --- |
| Vazamento entre empresas | consultas sem tenant, IDs aceitos sem contexto, cache/chaves globais e jobs sem escopo | TenantContext obrigatório no backend; filtros e FKs tenant-scoped; chaves de cache, arquivos, filas e eventos compostas por tenant; testes negativos de leitura e escrita cruzada |
| Publicação automática da LGPD | seed ou endpoint confundindo criação com publicação | create/seed sempre grava draft; somente comando autenticado publish do gestor altera published_version; constraint de uma versão publicada por tenant e auditoria do ator |
| Duplicidade de cliente | telefone sem normalização, comparação somente no frontend ou corrida entre importações | normalização única no serviço; índice único por tenant_id + phone_normalized; transação/constraint no backend; a API retorna conflito de domínio e a tela exibe o pop-up “Esse número já está cadastrado”, oferecendo abrir o cadastro existente |
| Sobrescrita de cliente | importador tratando linha como atualização automática | importação separa novo, já cadastrado, inválido e atualização autorizada; nenhuma atualização ocorre sem confirmação explícita e trilha de auditoria |
| Consentimento promocional indevido | importação copiando colunas ambíguas ou cadastro usando valor padrão verdadeiro | consentimento separado do cadastro; valor inicial false/null; somente ação explícita e auditada do gestor/cliente altera o campo; importação nunca concede consentimento |
| Métrica sem origem real | números calculados no frontend, fallback numérico, endpoint sem fonte persistida ou mistura de tenants | métrica calculada exclusivamente por query/serviço versionado; cada indicador possui definição, período, tenant e origem; ausência de dados retorna vazio; indisponibilidade retorna erro identificado |
| Métrica incorreta | filtros divergentes entre Marketing, CRM, BI e dashboard | serviço de consulta canônico e DTO compartilhado; mesma janela temporal/TTL; testes de reconciliação contra eventos e tabelas de origem |
| Quebra de rota/permissão | rota duplicada, alias removido, guard diferente do backend ou autorização somente visual | registro central de rotas/aliases; matriz RBAC única consumida por frontend e backend; testes de acesso direto, refresh, deep link e cada papel |
| Alteração financeira indevida | fórmula duplicada no frontend, mutação silenciosa ou migration sem reconciliação | fórmulas em serviço backend versionado; frontend apenas exibe; classificações e lançamentos preservados; qualquer mudança exige caso de negócio, revisão e reconciliação antes de persistir |
| Regressão em módulo compartilhado | alteração sem contrato, componente com comportamento implícito ou mudança sem cobertura | contratos tipados/aditivos, testes de componentes e integração, fixtures representativas e validação antes/depois em todos os consumidores |

Assim, “risco” deixa de ser critério de aceite. O critério passa a ser: a causa foi removida do caminho de execução e existe teste que demonstra o comportamento correto. Mensagens de conflito, como o telefone já cadastrado, são retornadas pelo backend com código de domínio estável e apresentadas pela interface sem criar outro registro.

### 6.2 Regras de exatidão operacional

- Nenhum dado de outro tenant pode ser retornado mesmo quando o identificador for conhecido.
- Nenhuma política LGPD pode ficar publicada sem comando explícito do gestor autorizado.
- Nenhum cliente pode ser criado quando o telefone normalizado já existir; o operador deve receber o pop-up e acessar o cadastro existente.
- Nenhum consentimento pode nascer de importação, inferência ou valor padrão afirmativo.
- Nenhuma métrica pode ser exibida sem consulta de origem identificada e período definido.
- Nenhuma alteração financeira pode alterar fórmulas ou históricos existentes sem versão, revisão e reconciliação.
- Nenhuma alteração de componente compartilhado pode ser liberada sem executar os consumidores afetados.

### 6.3 Evidência de exatidão

Cada métrica deverá possuir ficha de origem com nome, finalidade, fonte, consulta/evento, período, timezone, tenant, fórmula, tratamento de vazio, tratamento de indisponibilidade e horário de atualização. O valor exibido será reconciliável diretamente com os dados persistidos.

As permissões serão descritas por uma matriz única de superfície, ação e escopo: loja pública; pedido manual; Cozinha Preparo; KDS Pizzaiolo; Expedição; Motoboy; LGPD; CRM/Marketing; e Configurações. O frontend usará essa matriz para navegação e o backend para autorização efetiva, mantendo a mesma regra em acesso direto, refresh e mutações.

O cadastro/importação seguirá este fluxo:

```text
Telefone informado -> normalização no backend -> consulta no tenant
  -> não encontrado: cadastro
  -> encontrado: pop-up "Esse número já está cadastrado"
       -> usar cadastro existente | atualizar com confirmação | novo cadastro com justificativa
```

O mesmo telefone em formatos diferentes deverá localizar o mesmo cliente. O pop-up exibirá somente os dados necessários ao atendimento e registrará a decisão escolhida.

## 7. Resultado Esperado

Operação integrada em que venda manual desktop/mobile usa o mesmo catálogo e serviços; preparo transforma estoque com lote e validade; pizzaiolo trabalha por unidade com tempos persistidos e disputa de insumos segura; forno e embalagem são confirmados; expedição destaca bebidas e conclui somente a conferência física; pagamento é definido no atendimento e confirmado pelo fluxo responsável; impressão chega ao ambiente correto com falhas rastreáveis; entrega própria é distribuída com reserva segura; visitantes medem somente presença pública; instalação Motoboy fica restrita ao aplicativo.

**Status desta entrega:** plano revisado após alinhamento operacional; código de produto, migrations e configurações não alterados. A implementação começa após aprovação expressa deste plano. Os aceites funcionais permanecem futuros até a execução e a homologação de cada etapa.

## 8. Adendo — auditoria administrativa, sincronização e CRM

Este adendo incorpora o novo prompt ao mesmo plano, sem abrir uma arquitetura paralela. Ele cobre sincronização painel administrativo → loja, LGPD, Marketing Inteligência, CRM, cadastro/importação de clientes e padronização das abas de Gestão. Nenhum código de produto foi alterado nesta revisão.

### 8.1 Classificação do que já existe

| Módulo | Situação encontrada | Decisão do plano |
| --- | --- | --- |
| Sincronização painel → loja | Há serviços e telas existentes para tema, site config, operação da loja e catálogo; a causa da defasagem ainda precisa ser reproduzida por HTTP/browser autenticado | Auditar a fonte de verdade por tenant, cache, revalidação, permissões e estado; corrigir o caminho existente, sem criar outro cadastro de configuração |
| LGPD | `AdminLgpd`, `lgpdApi` e rotas públicas/admin já existem; a rota atual consulta políticas globalmente, `tenant_id` é anulável e o seed padrão ativa a política automaticamente | Evoluir para política tenant-scoped, versionada, editável e em rascunho até publicação explícita; preservar histórico e exigir autorização administrativa |
| Marketing Inteligência | Tela existente faz `Promise.all` de dashboard, campanhas, canais, funil, produtos, promoções e planejamento | Reproduzir cada contrato e corrigir envelope, schema, autenticação, vazio/nulo e dependências; não fabricar indicadores |
| CRM | Dashboard, inteligência, pipeline e tarefas possuem telas e rotas backend; parte do frontend usa `apiFetch` direto e `unwrap` local | Padronizar contratos pelo cliente API oficial e corrigir a causa real de cada resposta inválida, mantendo o fluxo comercial existente |
| Clientes | Listagem e consultas de identidade já existem; `AdminClientes` não expõe cadastro manual nem importação; `POST /customers` é público e exige e-mail | Criar fachada administrativa tenant-scoped, cadastro compatível com o modelo, importador CSV/XLSX e modelo de arquivo; não duplicar `Customer` |
| Estoque/CMV/Financeiro/Fiscal | Abas compartilhadas existem, mas Configuração é a primeira e o estado inicial é `settings` | Reordenar a navegação e o estado inicial preservando rotas, permissões e regras; auditar a finalidade e a integração das configurações antes de remover qualquer campo |
| CFAZ | Não foi encontrada ativação operacional comprovada no fluxo fiscal inspecionado | Documentar estado desabilitado e dependências; não habilitar nem implementar integração nesta etapa |

As mensagens genéricas “Resposta inválida da API” são sintomas a confirmar. O plano não presume que todos tenham a mesma causa: cada endpoint será observado com status HTTP, corpo, schema, logs, autorização e dependências reais.

### 8.2 Diagnóstico orientador

| Módulo | Problema | Causa a confirmar | Arquivos/superfícies | Solução proposta | Prioridade | Risco |
| --- | --- | --- | --- | --- | --- | --- |
| Loja | Alterações administrativas não chegam ao cliente | leitura estática, cache sem invalidação, tenant ausente ou estado duplicado | `client/context/AppContext.tsx`, `client/lib/api.ts`, tema/site config, produtos, `backend/routes/site_config.py`, operação da loja e produtos | matriz de fonte de verdade, versão/invalidação por tenant e teste salvar → ler → aplicar sem deploy | P0 | identidade ou horário incorreto em loja ativa |
| LGPD | Política padrão ausente, global ou publicada sem revisão | filtros globais, `tenant_id` anulável e seed ativo | `AdminLgpd.tsx`, `lgpdApi`, `backend/routes/lgpd.py`, `backend/models/customer.py` | rascunho padrão, publicação explícita, versão/histórico, endpoint público somente da política ativa do tenant | P1 | vazamento de política entre empresas ou publicação indevida |
| Marketing | Resposta inválida | endpoint/payload incompatível, falha parcial do `Promise.all`, permissão ou serviço externo | `MarketingIntelligence.tsx`, `client/lib/api.ts`, rotas/serviços Marketing | contratos versionados/aditivos, estados parciais e erro técnico rastreável | P0 | painel analítico indisponível ou números falsos |
| CRM dashboard/inteligência | Resposta inválida ou vazio tratado como falha | `unwrap` divergente, payload nulo, SQL opcional ou autorização | `CrmDashboard.tsx`, `CrmInteligencia.tsx`, `backend/routes/crm.py` | DTOs estáveis, vazio explícito, logs sem PII e testes de tenant/permissão | P0 | métricas incorretas |
| CRM pipeline/tarefas | Falha de carregamento ou persistência | contratos manuais, rotas CRUD divergentes ou estados vazios | `CrmPipeline.tsx`, `CrmTarefas.tsx`, `backend/routes/crm.py` | centralizar chamadas, validar transições e confirmar persistência real | P0 | alteração comercial perdida |
| Clientes | não há cadastro/importação acessível | superfície administrativa e APIs específicas ausentes | `AdminClientes.tsx`, `customersApi`, `backend/routes/customers.py` | cadastro manual, template exato, importação com prévia/mapeamento/lote/relatório | P1 | duplicidade, sobrescrita ou consentimento indevido |
| Gestão | Configuração aparece antes da operação | ordem e estado inicial hardcoded nas telas compartilhadas | `GestaoInventory.tsx`, `GestaoCmv.tsx`, `GestaoFinance.tsx`, `GestaoFiscal.tsx`, `AdminPageTabs`, `AdminGestao` | alterar arrays/estado inicial e auditar uso das configurações antes de qualquer remoção | P1 | link profundo ou permissão quebrada |

### 8.3 Etapas adicionais do plano

| Etapa | Entrega | Gate de saída |
| --- | --- | --- |
| F14 — sincronização administrativa | Mapear persistência e leitura de produtos, horários, cores, identidade e operação; corrigir cache/revalidação e escopo tenant | salvar no painel e observar na loja sem restart/deploy; produto desativado deixa de ser vendável; horário e tema aplicados |
| F15 — contratos Marketing/CRM | Reproduzir erros, alinhar schemas/envelopes e autenticação; separar indisponibilidade real de resposta vazia | cada tela carrega dados reais ou exibe causa identificável; nenhuma métrica simulada |
| F16 — clientes | Cadastro manual, duplicidade normalizada por tenant, CSV/XLSX, modelo, mapeamento, prévia, confirmação, lotes e relatório | importação idempotente quanto possível, sem sobrescrever indevidamente e sem conceder marketing consent |
| F17 — LGPD | Política padrão baseada nos dados empresariais, edição, prévia, rascunho, publicação/despublicação, versão e endpoint público tenant-scoped | seed nunca publica sozinho; versão ativa correta; histórico e consentimento referenciam versão |
| F18 — navegação Gestão | Reordenar Estoque, CMV, Financeiro e Fiscal; abrir aba operacional principal; preservar deep links e CFAZ desabilitado | ordem e aba inicial conferidas em desktop/tablet/mobile com RBAC |
| F19 — integração das configurações | Documentar parâmetros de Estoque, CMV, Financeiro e Fiscal e verificar consumidores, persistência e cálculos | cada configuração mantida tem uso identificado ou pendência explícita; fórmulas financeiras não mudam sem justificativa |
| F20 — regressão e relatório | Executar testes unitários, contratos, browser, segurança e integração dos módulos compartilhados | relatório final com causa, arquivos, testes, pendências e riscos remanescentes |

F14 e F15 são prioridades P0 e podem começar após o inventário de contratos. F16–F19 dependem da decisão arquitetural e dos schemas auditados. A implementação permanece bloqueada até aprovação deste plano, conforme a instrução do prompt.

### 8.4 Contratos, dados e segurança

- **Loja:** definir uma única fonte por tenant para produtos elegíveis, horário de funcionamento, cores, logo, título e demais configurações públicas. A leitura pública deve retornar somente o necessário à loja; credenciais e configurações internas permanecem privadas. Invalidar por tenant e versão/etag quando aplicável, sem exigir novo deploy.
- **LGPD:** consultas, criação, atualização, ativação e desativação devem filtrar `tenant_id`; somente uma versão ativa por tenant; geração padrão inicia como rascunho; publicação exige permissão e auditoria. A loja recebe apenas a versão publicada do próprio tenant.
- **Clientes/importação:** normalizar telefone/e-mail para detectar duplicidade no tenant; preservar registros existentes e exigir confirmação para atualização. Consentimentos de comunicação começam falsos/ausentes quando não informados. Restringir tamanho, extensão, encoding e conteúdo; bloquear fórmulas perigosas em planilhas; não registrar PII em logs.
- **Marketing/CRM:** toda resposta deve ter schema validado, estado vazio explícito e erro técnico rastreável. Falha de provedor externo deve ser informada como indisponibilidade, sem fallback numérico inventado. Rotas seguem RBAC e tenant do servidor.
- **Navegação:** usar os componentes compartilhados quando a alteração for realmente centralizada; preservar aliases e links diretos. Configuração é última aba; a primeira é a operação/indicadores definidos em cada módulo.

### 8.5 Arquivos, serviços e banco a auditar

`client/App.tsx`, `client/context/AppContext.tsx`, `client/lib/api.ts`, `client/pages/admin/AdminLgpd.tsx`, `client/pages/admin/AdminClientes.tsx`, `client/pages/admin/marketing/MarketingIntelligence.tsx`, `client/pages/admin/crm/CrmDashboard.tsx`, `CrmInteligencia.tsx`, `CrmPipeline.tsx`, `CrmTarefas.tsx`, `client/pages/admin/gestao/GestaoInventory.tsx`, `GestaoCmv.tsx`, `GestaoFinance.tsx`, `GestaoFiscal.tsx`, `client/components/admin/AdminPageTabs`, `AdminGestao`, `backend/routes/site_config.py`, `backend/routes/customers.py`, `backend/routes/lgpd.py`, `backend/routes/crm.py`, rotas/serviços Marketing e Inteligência, `backend/services/gestao_service.py`, modelos de tenant, customer, LGPD e configurações. A lista é ponto de partida; a implementação deve confirmar os arquivos efetivamente usados antes de editar.

Migrations só serão criadas se a auditoria provar necessidade: isolamento/constraints de LGPD, versão/publicação, importação auditável ou cache/versionamento persistido. Nenhuma migration histórica será editada e nenhum dado será apagado para “corrigir” a sincronização.

### 8.6 Testes e critérios de aceite adicionais

| Grupo | Critérios verificáveis |
| --- | --- |
| Sincronização | salvar horário, cor, identidade e produto no painel; ler pela loja no mesmo tenant; produto inativo não entra em novo pedido; sem restart/deploy; cache e revalidação comprovados |
| LGPD | gerar padrão sem publicar; pré-visualizar/editar/salvar; publicar/despublicar explicitamente; política pública correta por tenant; versões antigas preservadas; versão do consentimento rastreável |
| Marketing/CRM | contratos de todos os endpoints consumidos; 200 vazio, nulo, 401/403 e falha externa; dashboard/pipeline/tarefas persistem alterações; sem “sucesso” com dados fictícios |
| Clientes | botão visível; criação e duplicidade; CSV/XLSX válido, inválido, colunas mapeadas, prévia, rejeições com linha/motivo, lotes, template igual ao schema; nenhum consentimento promocional automático |
| Navegação | Estoque abre Insumos; CMV Indicadores; Financeiro Resumo DRE; Fiscal preserva ordem relativa e Configuração por último; deep links, RBAC, responsividade e aba ativa |
| Regressão | KDS, pedidos, logística, catálogo, BI, dashboard, loja e integrações compartilhadas continuam operacionais; CFAZ permanece desabilitado |

### 8.7 Fora do escopo deste adendo

Não habilitar CFAZ, não trocar fórmulas financeiras sem evidência, não recriar CRM/catálogo/estoque existentes, não publicar automaticamente política LGPD, não conceder consentimento promocional pela importação e não transformar erro de serviço externo em dados simulados. O prompt pede diagnóstico antes de implementação; portanto a próxima autorização deve liberar a execução das etapas F14–F20, e não uma alteração parcial sem os gates correspondentes.

## 9. Resultado consolidado após o novo prompt

O plano agora cobre os três prompts operacionais anteriores e este quarto conjunto administrativo. A ordem recomendada é: E0/F14–F15 (contratos e sincronização), E1–E2 (segurança operacional, visitantes e PWA), F16–F17 (clientes e LGPD), E3–E10 (venda, preparo, impressão e entrega), F18–F19 (navegação e configurações), E11–E12/F20 (indicadores, regressão e homologação). Essa ordem pode ser ajustada pelo Arquiteto após a reprodução dos contratos, sem criar writers concorrentes.

**Status documental:** diagnóstico e plano ampliados; nenhum código de produto, migration, configuração ou deploy foi alterado. A implementação só começa após aprovação expressa do plano atualizado.

## 10. Registro da execução inicial

Execução autorizada em 26/10/2026. Primeira rodada concluída:

- Sincronização painel → loja: atualização de CMS, configuração de sabores, foco/visibilidade, mudança de tenant e prevenção de requests sobrepostos.
- Marketing/CRM: dashboards migrados para o cliente API central; métricas ausentes não são preenchidas com zero fictício.
- Clientes/LGPD: telefone normalizado, índice único por tenant, conflito CustomerPhoneConflict, cadastro administrativo tenant-scoped e políticas LGPD tenant-scoped em rascunho até publicação explícita.
- Gestão: abas operacionais primeiro e Configuração por último em Estoque, CMV, Financeiro e Fiscal.
- Visitantes: rastreamento limitado a rotas públicas de venda no frontend e backend.
- E1 KDS/estoque: timer persistido de cinco segundos, consumo FIFO transacional, estado aguardando_analise, retorno ao atendimento, cobertura legada e gates de liberação no pedido/entrega.
- E1 pagamento/Expedição: projeção somente leitura de situação, provedor e troco; retirada incluída; nenhum pagamento presumido por pay_on_delivery.
- E2 visitantes/PWA: presença explícita somente na loja pública, heartbeat com TTL e deduplicação por visitante/aba; manifesto, registro e metadados do Motoboy isolados no escopo `/motoboy/`, sem interceptação da loja, painel, TV ou APIs.
- E3 venda manual: composer compartilhado em desktop e mobile, botão **Fazer Pedido** em Operações, rota `/operacoes/novo-pedido`, busca/cadastro de cliente, catálogo Product reutilizado, quote server-side, pagamento com forma/situação separadas, troco e criação idempotente tenant-scoped no fluxo operacional.
- E4 comprovante operacional: projeção compartilhada de bebidas no pedido/KDS, bloco destacado para conferência, pagamento separado entre forma/situação, troco calculado a partir dos dados persistidos, origem/modalidade, checklist de expedição e logo tenant configurável; prévia e impressão de teste aguardam o carregamento do logo e usam o caminho de impressão existente.

Validação desta rodada: typecheck TypeScript aprovado; build do cliente, worker, servidor e Capacitor aprovados; 13 testes Vitest de E2 (presença/PWA) aprovados; 7 testes backend de presença aprovados; testes de branding/PWA do agente aprovados; testes frontend de E1 aprovados; 26 testes KDS/estoque aprovados; 17 testes backend de pagamento aprovados; 10 testes frontend de pagamento/impressão aprovados; head Alembic único em 20261026_kds_stock_gate; `git diff --check` sem erros.

Validação E3: 39 testes Vitest de API, produto, composer e pagamento/impressão aprovados; 14 testes backend de pedidos/cliente/order-board aprovados; 24 testes de schema/runtime aprovados (5 skips dependentes de PostgreSQL); typecheck, build cliente/worker/servidor e head Alembic único em `20261026_manual_order_actor_audit`.

Validação E4: 36 testes Vitest de impressão/API aprovados; 18 testes backend de projeção do comprovante, KDS e pagamento aprovados; `compileall` dos serviços alterados aprovado; typecheck TypeScript, build do cliente/worker e build do servidor aprovados; projeção KDS agora entrega `product_type`, `is_drink`, `drinks` e `has_drinks` sem classificação por nome; nenhuma migration nova foi necessária.

Lote 1: E5 avançou com validação do contrato de transporte de impressoras (`network_host`, porta, protocolo e serviço local) sem declarar acesso direto do navegador a IP; E6 avançou com a decisão explícita `portionable` por linha de entrada, geração idempotente de ordem de preparo e migration `20261026_inventory_portionable`; F16 avançou com importação CSV/XLSX tenant-scoped, prévia, confirmação, modelo CSV e rejeição por telefone duplicado sem sobrescrita ou consentimento promocional. A execução transacional completa do preparo, consumo bruto, entrada de preparados, lote/validade e etiquetas vinculadas ao `execution_id` permanece bloqueada até o contrato de transformação de estoque e etiquetas ser fechado.

Lote 2: E7 concluído com transformação transacional, consumo bruto, entrada do preparado, lote/validade, gramatura, responsável, rollback e idempotência; etiquetas de preparo agora possuem entidade própria vinculada a `execution_id`, impressão inicial idempotente e reimpressão com motivo sem movimentar estoque. E8 foi validado pelos contratos existentes de unidades, timer de cinco segundos, reserva concorrente, forno e exceção de estoque; o painel de preparo passou a abrir a prévia e impressão das etiquetas pelo renderer compartilhado. A consulta histórica de execuções após recarregar a tela ainda depende de endpoint de listagem de execuções.
Lote 3: núcleo E9/E10 concluído no backend e na projeção da Expedição. A liberação para expedição/retirada agora exige que todas as unidades físicas estejam prontas; a atribuição usa locks tenant-scoped e estados explícitos de coleta e entrega, com retorno/falha liberando reatribuição. A Expedição exibe bebidas em bloco próprio e pagamento somente como projeção dos dados reais, sem alterar ou presumir quitação. O checkbox de confirmação de cobrança permanece exclusivamente no aplicativo do motoboy quando o contrato exigir pagamento na entrega. Timeout automático continua dependente do serviço de alertas existente; não foi criado um worker paralelo. O checklist/embalagem persistido por unidade ainda exige contrato de dados próprio antes de ser declarado concluído.

Lote 4: E11 implementado com planejamento semanal PCP tenant-scoped, sugestões calculadas somente por pedidos entregues reais, janela histórica configurável, rascunho revisável e aprovação explícita com gestor, ator e timestamp. O painel foi integrado ao Planejamento de Preparo com loading, vazio, erro e permissões; não cria produção automaticamente nem inventa métricas de capacidade. Indicadores existentes continuam sendo derivados dos eventos persistidos.

Pendências para as próximas rodadas: integração visual dos alertas stock-alerts no Atendimento/Gerência, concorrência real em PostgreSQL descartável, conectar o popup de telefone ao pedido manual, implementar importação CSV/XLSX, preparo/porcionamento, impressão em rede e homologação com PostgreSQL/equipamentos reais. A ponte de um registro raiz antigo com push é preservada até existir migração de inscrições; Android/iOS, HTTPS, dispositivos reais e migrations ainda não foram homologados/aplicados em produção.



