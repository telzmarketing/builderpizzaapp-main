# BI Mobile — diagnóstico, implementação e validação

Data da revisão: 27/10/2026. Rota preservada: `/painel/bi-mobile`.

## Diagnóstico inicial

A tela `client/pages/admin/bi/BiMobile.tsx` consultava `GET /api/bi/mobile`
a cada dez segundos, sem navegação por abas nem proteção contra respostas fora
de ordem. Reunia visitantes, pedidos, faturamento e WhatsApp. Não apresentava
pizzas, ticket, pagamentos, evolução comparativa, histórico mensal ou análise
gerencial. Visitantes únicos apareciam como acessos e a configuração do chatbot
era interpretada como chatbot online.

A arquitetura existente oferece React 18, TypeScript, Tailwind, componentes
shadcn, Recharts, FastAPI, SQLAlchemy e PostgreSQL. Foram reutilizados
`TelzLogo`, Dialog, tokens visuais e o cliente `client/lib/api.ts`.
As rotas continuam sob autenticação administrativa e contexto confiável de
empresa. O serviço original de BI permanece disponível para os consumidores
existentes.

O projeto já tinha heartbeat público de presença com saída, sequência por aba,
deduplicação e expiração. A nova consulta utiliza esse mecanismo em vez de
interpretar qualquer evento de analytics como presença. A allowlist de páginas
públicas é a mesma do módulo de visitantes.

## Escopo e decisões aprovadas

- Quatro abas: Pedidos, Atendimento, Evolução e Geral. Pedidos é a inicial.
- Receita confirmada segue o BI existente: `Order.total` de pedidos com
  pagamento `approved`/`paid`, excluindo cancelados e estornados.
- Séries, ticket, pizzas e comparativos usam o mesmo conjunto de pedidos pagos.
  Pedidos criados, cancelamentos e previsão são apresentados separadamente.
- A existência de pagamento é verificada por `EXISTS`, evitando multiplicar
  pedidos por pagamentos repetidos em bases legadas.
- Pizza é a quantidade do item físico, sem multiplicar sabores. Bebidas e
  adicionais são excluídos. Produtos sem tipo só utilizam categorias explícitas
  de pizza; nomes e categorias contendo apenas a palavra pizza não bastam.
- O dia civil de São Paulo, já utilizado pelo histórico do BI, foi preservado e
  identificado na tela. Os horários de funcionamento existem para abertura da
  loja, mas não definem fechamento contábil do BI. Uma venda após meia-noite
  pertence ao novo dia civil; não foi criada outra regra histórica.
- A data principal é referência de Pedidos/Atendimento e da Evolução enquanto
  seu filtro específico não for alterado. Geral tem períodos encerrados hoje,
  explicitamente independentes. Alternar abas preserva os filtros.
- Datas futuras são rejeitadas no serviço e bloqueadas no calendário.
- Mesmo dia do mês anterior é limitado ao último dia existente. Janelas móveis
  mantêm a duração; as datas efetivamente comparadas e a regra ficam visíveis.
- Comparação parcial é opcional na Evolução e usa o mesmo horário em ambos os
  períodos. Percentual com base anterior zero fica sem base comparável.
- Geral compara 7/30/90 dias com a janela imediatamente anterior; mês atual com
  o período correspondente do mês anterior. O período atual em andamento é
  identificado.
- Não foram alterados checkout, regras financeiras, autenticação ou ingestão
  de canais externos. Não foram criadas entidades comerciais paralelas.

## Mapa das fontes persistidas

| Indicador/domínio | Fonte e relacionamento | Critério |
| --- | --- | --- |
| Pedidos, status, valores e origem | `orders`, chave interna e `sales_channel` | Empresa + criação no período |
| Pagamentos | `payments.order_id` → `orders.id` | Empresa em ambos; confirmação sem duplicação |
| Pizzas e sabores | `order_items.order_id`, `product_id`, `quantity`; `order_item_flavors` | Contar item físico; sabores não multiplicam |
| Produtos | `products.product_type` e categorias legadas explícitas | Empresa também no produto vinculado |
| Kits | `promotional_kits` → `promotional_kit_items` | Cadastro existe; sem composição histórica de kit no pedido |
| Clientes identificados online | `visitor_profiles.customer_id` | Apenas visitantes com heartbeat público vigente |
| Visitantes únicos e acessos | `visitor_profiles`, `visitor_events`, `visitor_sessions` | Pessoas distintas versus quantidade de sessões públicas |
| Presença pública | eventos `store_presence`/`store_presence_leave` | Sequência por aba, TTL e isolamento por empresa |
| Chatbot | `chatbot_conversations`, `chatbot_messages` | Estado aberto + mensagem nos últimos cinco minutos para online |
| Atendimento histórico | início das conversas da loja e das sessões WhatsApp | Período selecionado; sem deduplicar pessoa entre canais |
| Duração média | início/fim de conversas encerradas do chatbot | Apenas timestamps válidos; fonte informada na interface |
| WhatsApp atual | `AgenteWhatsAppService.operational_metrics` | Contexto confiável e tabelas já vinculadas à empresa |
| Operadores disponíveis | Sem fonte comprovada de presença do atendimento | Indisponível; login ou conversa recente não provam disponibilidade |
| IA | Configuração da empresa e factory existente `services/ai/factory.py` | Configuração não equivale a conversa em andamento |
| Histórico mensal | Agregação dos mesmos pedidos/pagamentos | Sem tabela de faturamento paralela |

As relações e constraints existentes incluem IDs internos únicos, referências
externas únicas por empresa e pagamento canônico por pedido. As consultas novas
aplicam empresa nos pedidos, pagamentos, itens e produtos. Não retornam dados
pessoais nos gráficos.

## Backend e contratos adicionais

`GET /api/bi/mobile/analytics` aceita:

| Parâmetro | Valores |
| --- | --- |
| `date` | Data ISO opcional, padrão hoje |
| `period` | `today`, `7d`, `30d`, `90d`, `month` |
| `compare` | `previous_month`, `previous_period`, `none` |
| `partial` | Booleano |
| `monthly` | `6m`, `12m`, `year`, `previous_year` |
| `view` | `all`, `orders`, `attendance`, `evolution`, `general` |
| `grouping` | `day`, `week`; uma data continua agrupada por hora |

Retorna período, critérios, totais, comparativos, séries, pagamentos, canais,
histórico mensal e atendimento. `view` evita consultas de atendimento e histórico
mensal nas abas que não os utilizam. As séries são agregadas no SQL; não são
enviados milhares de pedidos ao navegador para calcular indicadores.

`POST /api/bi/mobile/analyze` recebe os mesmos filtros em JSON. Retorna resumo,
fatos, tendências, pontos de atenção, recomendações e identificação do motor.
Nenhum dos dois endpoints aceita selecionar empresa pelo payload.

Os contratos anteriores (`/mobile`, `/dashboard`, `/sales`, `/run-analysis` etc.)
foram preservados. As respostas seguem o envelope `success/data` existente e
validação Pydantic.

## Análise gerencial e IA

Os fatos, números, diferenças, dia de maior/menor receita e horários de pico são
calculados pelo serviço. As recomendações elegíveis derivam desses resultados.
Quando a configuração de IA da empresa está ativa e um provedor está disponível,
a factory existente pode priorizar **somente IDs das recomendações elegíveis**.

A resposta deve conter exatamente os IDs permitidos, sem repetição. Texto livre,
IDs inventados, erro de provedor ou JSON inválido acionam o relatório calculado.
Nenhum número ou conclusão livre gerado pelo modelo é mostrado. São enviados
apenas filtros, indicadores agregados e ações estáticas, sem telefone, nome,
endereço ou mensagens de clientes. Não há uma segunda integração de IA.

`engine=calculated` indica análise por regras; `engine=ai_assisted` indica apenas
priorização assistida. A nota correspondente é exibida no relatório.

## Frontend e atualização

Componentes reutilizáveis em `client/components/bi/` oferecem cartões, filtros,
gráficos e tooltips com valores atuais/anteriores e diferenças. Evolução usa
verde `#22C55E` e amarelo `#EAB308`. Geral inclui agrupamento semanal para 90 dias,
histórico mensal com tabela de detalhes e botão Analisar.

Polling padrão de 30 segundos, configurável por `VITE_BI_REFRESH_MS` com mínimo
de dez segundos. Requisições simultâneas da mesma chave são deduplicadas;
respostas antigas não substituem filtros recentes. O cache é limitado e
revalidado quando vencido. Atualização periódica pausa em documento oculto.
A troca de empresa existente recarrega a aplicação, descartando o cache local.

Loading, erro inicial, falha de refresh com dados anteriores identificados,
ausência de registros e informação indisponível têm apresentações distintas.
Falhas não são convertidas em indicadores zerados. Analisar usa POST sem retry
automático.

## Banco e publicação

A migration forward `20261027_bi_mobile_analytics_indexes` acrescenta cinco
índices compostos: empresa/criação de pedido, empresa/criação de evento,
empresa/início de sessão e empresa/início e encerramento de conversa.
Metadata e referências operacionais de Alembic acompanham o novo head.
Não altera nem reconstrói registros comerciais.

Os índices são construídos pelo caminho transacional do projeto. Em tabelas
grandes, sua criação pode bloquear escritas; publicar exige janela operacional
adequada e ensaio no clone da base real. O código anterior ao novo índice
permanece compatível; o par direcional foi registrado nas regras de recuperação.

## Evidências de validação local

- Base PostgreSQL 15 descartável criada separadamente e migrada do zero pelo
  Alembic; atualização para o novo head aplicada e confirmada.
- Testes backend cobrem pagamentos duplicados, empresa em todos os vínculos,
  cancelamento/estorno, quantidade de pizzas, exclusão de bordas/adicionais,
  virada UTC/local, comparação parcial, fevereiro/bissexto/ano, períodos vazios,
  SQL PostgreSQL, séries/totais/pagamentos, agrupamento semanal, visitantes e
  atendimento histórico versus presença atual.
- Testes de acesso HTTP verificam 401 anônimo, 422 para filtros inválidos e
  impossibilidade de selecionar outra empresa por query/body.
- Testes de IA verificam priorização válida, IDs inventados/repetidos, formato
  inválido e rejeição de prosa com números fabricados, sem chamada externa.
- Suíte frontend: 41 arquivos, 212 testes aprovados; TypeScript aprovado.
- Build de cliente, service worker, servidor e preparação Capacitor aprovado.
- Navegador Edge automatizado: abas, filtros 7/30/90/mês, agrupamento semanal,
  filtros mensais, comparação verde/amarela, análise e falha controlada de
  atualização. Testes em 360 px e desktop, sem exceções JavaScript.
- Capturas locais de QA em `.runtime/bi-mobile-browser/`. A aplicação de teste
  usa pedidos persistidos exclusivamente no PostgreSQL descartável; o override
  de autenticação pertence ao harness ignorado em `.runtime`, não ao produto.

Os testes backend podem ser reproduzidos com a variável
`DRIVER_SCHEMA_TEST_DATABASE_URL` apontando para uma base descartável migrada e
`python -m pytest tests/test_bi_mobile_analytics.py tests/test_bi_mobile_security.py
tests/test_bi_migrated_postgresql.py tests/test_wave6_bi_marketing_intelligence_tenant.py
tests/test_storefront_presence.py -q -p no:cacheprovider`.

## Limites e dependências reais

- Não há uma fonte de presença para disponibilidade de operadores humanos do
  atendimento; o indicador permanece explicitamente indisponível.
- Kits existem no cadastro, mas o fluxo atual não persiste composição de kit
  no pedido. Componentes efetivamente registrados são contados; reconstrução
  de combos históricos opacos depende de evolução do checkout, fora desta
  mudança do BI.
- Contratos preparatórios de marketplace não comprovam ingestão ativa de
  iFood, 99Food ou Keeta. Pedidos já integrados em `orders` entram uma vez;
  taxas, subsídios e repasses ausentes não são estimados.
- Ausência de registros não comprova importação completa. O BI declara que
  utiliza o histórico persistido, sem certificar dados externos não importados.
- A média histórica auditável utiliza conversas encerradas do chatbot. O
  WhatsApp atual não fornece timestamp imutável de encerramento equivalente.
- A regra de dia civil foi mantida; não foi introduzido corte operacional após
  meia-noite nem configuração de timezone paralela ao BI existente.
- Priorização de IA foi validada com provedor substituído em testes. Uma chamada
  real ao provedor depende da configuração da empresa e não foi executada.
- Não houve commit, push, execução de CI remoto, deploy ou validação na VPS.
