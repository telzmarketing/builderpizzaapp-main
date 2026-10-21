# Auditoria de produtos e operação — 20/10/2026

## 1. Resumo executivo

**O cadastro comercial é compartilhado, mas a operação completa dos produtos não está validada e apresenta defeitos de exibição, configuração, autorização, precificação e consumo.**

Escopo interpretado a partir da conversa: ciclo completo dos produtos, do cadastro à venda e operação. Esta não é uma auditoria irrestrita de todos os recursos do SaaS, infraestrutura ou provedores externos.

Revisão no checkout `259f3cbe3345cfff69643ebc67a5f51a75f89e6a`, considerando também o estado de trabalho existente. Nenhum arquivo de aplicação foi corrigido. Este documento é o único artefato criado pelo orquestrador; testes e build geraram seus artefatos locais habituais.

As alterações preexistentes em `.claude`, os contratos não rastreados de marketplaces e `tests/test_marketplace_contracts.py` foram preservados. Código não rastreado não é evidência de funcionalidade publicada.

### Critério de evidência e prioridade

- **Reproduzido isoladamente:** execução do método/componente real com dados controlados, sem PostgreSQL ou navegador real.
- **Confirmado no código:** caminho de execução identificado; impacto em dados reais ainda depende de execução integrada.
- **Condicionado:** depende de configuração, regra de negócio ou estado do banco que não foi comprovado.
- **P1:** corrigir antes de aprovar operação completa; afeta venda, autorização ou integridade operacional.
- **P2:** corrigir para consistência, recuperação administrativa e diagnóstico.

As propostas abaixo são critérios para uma futura correção; não representam alterações já executadas.

## 2. Responsáveis e método

Orquestrador: escopo, revisão da estrutura, validação local e consolidação.

Agentes de apoio: Frontend; Backend/Database; Operação. Foram revisados os papéis locais em `agents/`, a estrutura React/Context/API, FastAPI/services, models/schemas, migrations Alembic e testes existentes.

Fluxo encontrado:

```text
Cadastro de produtos → tabela products e opções
  ├─ Loja → AppContext → home/cardápio/produto → carrinho → checkout
  ├─ Salão → comanda → gerar pedido → confirmar pagamento
  └─ WhatsApp → ferramentas → OrderService
                     ↓
             Order / OrderItem
              ├─ cozinha / KDS
              ├─ expedição e entrega/retirada
              ├─ snapshots de CMV / baixa e estorno
              └─ BI e relatórios
```

## 3. Cobertura por módulo

| Área | Integração encontrada | Limite principal |
|---|---|---|
| Cadastro | Mesma tabela canônica consumida pela loja | Inativos inacessíveis na tela padrão; RBAC insuficiente |
| Home | API real, seleção por categoria/produto, promoções e fallback sem categoria | Filtro de delivery não enviado; erro pode parecer vazio |
| Cardápio | Catálogo do AppContext | Sem categoria pode sumir; alias `/menu` não dispara carga |
| Produto | Tamanhos, massas, bordas e composição de pizzas | Crash sem produto; borda perde ID; bebidas não oferecem opções |
| Carrinho/checkout | Snapshot frontend; recálculo server-side | Divergência de seleção/preço; validação de IDs incompleta |
| Salão administrativo | Produtos ativos `dine_in`; materializa pedido real | Sem opções estruturadas e sem conclusão operacional adequada |
| Salão público | HTML e CMS próprios | Não sincroniza automaticamente o cardápio com `products` |
| Pedidos | Mostra produtos vendidos e sabores | Depende da materialização do pedido |
| Cozinha/KDS | Carrega itens e resolve produtos por tenant | Canal salão rotulado como entrega em uma tela |
| Expedição | Produtos/sabores de entrega e retirada | Salão excluído da logística; precisa conclusão própria |
| Estoque/fichas | Receitas no editor de produtos; baixa/estorno implementados | Frações, fichas parciais e validação agregada |
| CMV | Consulta catálogo e congela snapshots por pedido | Composição parcial pode parecer completa |
| BI | Itens de vendas pagas e não canceladas | Não deve listar todo produto cadastrado como venda |
| WhatsApp | Catálogo e criação via OrderService | Configuração/provedor/conversa real não validados |
| PDV independente | Não localizado nas rotas/telas pesquisadas | Não declarar módulo separado operacional |
| Marketplaces | Contratos locais e binding de tenant | Não localizada operação de adapter/rota/tela completa |

Evidências de integração: `backend/main.py:1365`; `client/pages/Index.tsx:87`; `backend/routes/salao.py:170`; `backend/services/order_service.py:927`; `backend/services/kds_service.py:74`; `backend/services/agente_whatsapp_tools.py:396` e `:639`; `backend/services/business_intelligence_service.py:311`.

## 4. Achados de exibição e administração

### F01 — P1: página de produto quebra antes do carregamento

- **Cenário:** acesso direto a `/product/:id` com cache vazio, ou ID ausente do catálogo.
- **Causa:** `product = products.find(...)` pode retornar `undefined`, mas `product.inventory_available` é lido antes dos guards de carregamento e produto inexistente.
- **Evidências:** `client/pages/Product.tsx:345`, `:707`, `:710`, `:721`.
- **Validação:** arquivo real transpilado em memória e renderizado com ReactDOMServer, contexto `products=[]`, `loading=true`: `TypeError: Cannot read properties of undefined (reading 'inventory_available')`.
- **Aceite de correção:** acesso sem cache mostra carregamento; produto inexistente mostra estado apropriado; nenhum erro de renderização.

### F02 — P1: acesso direto a `/menu` delivery não carrega catálogo

- **Cenário:** abrir `/menu` sem ter visitado a home e sem cache.
- **Causa:** a rota renderiza `Cardapio`, mas bootstrap e refresh não incluem `/menu`.
- **Evidências:** `client/App.tsx:541`; `client/context/AppContext.tsx:518` e `:534`.
- **Validação:** funções reais executadas em memória retornam `products:false` para `/menu`, e `true` para `/cardapio`.
- **Aceite:** aliases que mostram catálogo carregam e atualizam os mesmos dados.

### F03 — P2: produtos inativos não ficam disponíveis para recuperação administrativa

- **Cenário:** remover/inativar produto e depois tentar localizá-lo e reativá-lo na tela de produtos.
- **Causa:** administração usa o mesmo array do contexto, carregado com `list(true)`; exclusão apenas altera `active=False`.
- **Evidências:** `client/pages/admin/Products.tsx:194` e `:1432`; `client/context/AppContext.tsx:621`; `backend/routes/products.py:559`.
- **Validação:** leitura cruzada do carregamento, filtro da tela e exclusão lógica.
- **Aceite:** administração lista inativos com filtro e permite reativar, preservando histórico.

### F04 — P2: produtos sem categoria desaparecem do cardápio

- **Causa:** abas são extraídas apenas de produtos categorizados; filtro exige categoria selecionada e correspondente.
- **Evidências:** `client/pages/Cardapio.tsx:29` e `:57`; comparação com fallback da home em `client/lib/homeCatalog.ts:31`.
- **Aceite:** produto ativo sem categoria permanece alcançável em catálogo misto e totalmente sem categorias.

### F05 — P2: falha da API pode ser apresentada como catálogo vazio

- **Causa:** contexto marca carregamento encerrado mesmo na rejeição; a tela apresenta mensagem de ausência de produtos.
- **Evidências:** `client/context/AppContext.tsx:628`, `:717`; `client/pages/Cardapio.tsx:156`; `client/pages/Index.tsx:443`.
- **Aceite:** diferenciar erro, carregamento e catálogo realmente vazio; oferecer recuperação visível.

## 5. Achados de venda, configuração e autorização

### F06 — P1: visibilidade de delivery não é imposta em todo o fluxo

- **Cenário:** produto ativo com `visible_delivery=false` ainda aparece na loja; envio direto também pode ser aceito.
- **Causa:** frontend não envia `channel=delivery`; detalhe e validação do pedido não verificam essa visibilidade.
- **Evidências:** `client/context/AppContext.tsx:621`; `client/lib/api.ts:5034`; `backend/routes/products.py:341` e `:357`; `backend/services/order_service.py:290` e `:320`.
- **Aceite:** impor canal no backend para listagem, detalhe/cotação aplicável e criação; não depender apenas de ocultar cartões.

### F07 — P1: preço exclusivo de delivery não é utilizado na precificação

- **Cenário:** cadastrar preço-base e `delivery_price` diferentes e vender pela loja.
- **Causa:** campo existe no cadastro, mas não participa do serviço de precificação nem do OrderService; cálculo utiliza preço do tamanho ou do produto.
- **Evidências:** `backend/schemas/product.py:132`; `backend/services/product_pricing_service.py:152`; `backend/services/order_service.py:395`. Salão utiliza `dine_in_price` em `backend/services/salao_service.py:233`.
- **Aceite:** definir precedência por canal/tamanho/promoção e garantir o mesmo valor em exibição, cotação, pedido e pagamento.

### F08 — P1: checkout aceita IDs inválidos ou ausentes de opções

- **Cenário reproduzido:** produto-base R$30, tamanho Grande R$80; enviar rótulo Grande com ID inválido devolveu preço R$30, sem rejeição. IDs de massa/borda/variante inválidos também foram ignorados.
- **Causa:** consultas sem resultado deixam opção nula e permitem fallback; nomes fornecidos pelo cliente são persistidos.
- **Evidências:** `backend/services/order_service.py:307`, `:338`, `:364`, `:381`, `:762` e `:766`.
- **Validação:** método real `_validate_item` executado com consultas e disponibilidade controladas, sem banco; retorno `30.0`.
- **Aceite:** rejeitar IDs inexistentes, inativos ou de outro produto/tenant; exigir opções obrigatórias; derivar nomes e preços das referências validadas. Omissão válida em produto simples deve continuar funcionando.

### F09 — P1: borda paga perde identidade entre produto e checkout

- **Cenário:** escolher massa e borda com adicional separado.
- **Causa:** frontend soma o adicional, mas guarda apenas o ID da massa; concatena a borda no texto. Backend cobra somente a opção identificada.
- **Evidências:** `client/pages/Product.tsx:562`, `:658`; `client/pages/Checkout.tsx:659`; `backend/services/order_service.py:364` e `:593`.
- **Impacto:** total exibido pode exceder o total efetivamente calculado; produção/receita perde referência estruturada da borda.
- **Aceite:** preservar todas as seleções estruturadas e calcular os adicionais no backend, sem quebrar contratos publicados.

### F10 — P1: bebidas configuráveis não oferecem seleção correspondente na loja

- **Cenário:** cadastrar volume/tamanho e variante normal/zero ou opção com adicional.
- **Causa:** tela de produto pula carregamento/seletor de tamanhos para bebida e envia variante nula. Adição rápida de não pizzas também ignora essas opções.
- **Evidências:** `client/pages/admin/Products.tsx:1281` e `:2440`; `client/pages/Product.tsx:420`, `:676`, `:880`; `client/pages/Cardapio.tsx:70`.
- **Aceite:** opções cadastradas e obrigatórias selecionáveis; adição rápida somente quando houver configuração válida e inequívoca.

### F11 — P1: mutações de catálogo não exigem permissão específica de RBAC

- **Cenário:** administrador autenticado com papel comum sem edição de produtos chama API diretamente.
- **Causa:** CRUD de produtos/categorias/opções/promoções exige `get_current_admin`, sem verificação de permissão do recurso. A autenticação restringe suporte e papéis KDS, mas não substitui RBAC para os demais papéis.
- **Evidências:** `backend/routes/products.py:264`, `:453`, `:529`; `backend/routes/admin_auth.py:58`; `backend/core/kds_station_access.py:7`; `backend/main.py:1290`.
- **Validação:** árvore de dependências FastAPI inspecionada; handlers selecionados contêm autenticação/banco, sem dependência RBAC. Não foi executada mutação com conta real.
- **Aceite:** API nega leitura/mutação conforme permissões existentes, incluindo testes de negação; esconder botão não atende o requisito.

## 6. Achados de salão, produção, estoque e CMV

### F12 — P1: comanda não representa opções estruturadas do produto

- **Causa:** item de comanda recebe produto, quantidade, preço e observação; materialização fixa tamanho `Salao`, IDs de tamanho/massa nulos e divisão 1.
- **Evidências:** `backend/schemas/salao.py:149`; `backend/services/order_service.py:998`; `client/pages/admin/salao/AdminSalao.tsx:475`.
- **Impacto:** configuração, preço, produção e ficha específica podem divergir da venda delivery.
- **Aceite:** preservar referências e composição necessárias à venda e à operação sem criar catálogo paralelo.

### F13 — P1: pedido de salão pronto não dispõe de conclusão operacional coerente

- **Causa:** cozinha avança para `ready_for_pickup`; conclusão de retirada rejeita `dine_in`; expedição o exclui; máquina de estados só permite avançar para `on_the_way`. Tela de pedidos oferece atribuição de motoboy nessa situação.
- **Evidências:** `backend/services/kds_service.py:205`, `:217`, `:238`; `backend/core/state_machine.py:37`; `client/pages/admin/Orders.tsx:952` e `:1146`.
- **Distinção:** confirmar pagamento fecha a comanda, mas não conclui o status operacional do pedido. Excluir salão da logística de entrega é intencional; falta o fluxo próprio de serviço/conclusão.
- **Aceite:** definir e validar caminho de pedido servido/concluído usando a autoridade de transições existente.

### F14 — P1: consumo e CMV de múltiplos sabores são assimétricos

- **Cenário:** uma pizza A+B com fichas de 100g por pizza inteira deveria aplicar a fração correspondente a cada sabor; o algoritmo aplica A inteiro e B dividido.
- **Evidências:** `backend/services/cmv_snapshot_service.py:254` e `:264`; `backend/services/inventory_service.py:609` e `:978`.
- **Validação:** método real `_recipe_uses` extraído e executado em memória retornou `[('A', 1.0), ('B', 0.5)]` para quantidade 1 e divisão 2.
- **Impacto:** mudar qual sabor é principal muda consumo/CMV da mesma composição. O modelo também não distingue adequadamente base inteira e ingrediente proporcional do sabor.
- **Aceite:** explicitar referência da ficha e papel dos componentes; a mesma composição deve ter o mesmo consumo independentemente da ordem dos sabores; validar inteira, duas e três partes.

### F15 — P1: ficha ausente em um componente não é sinalizada

- **Causa:** `missing_recipe = not recipe_uses`; se A tem ficha e B não, a lista de A mascara a ausência de B. Baixa prefere snapshot não vazio mesmo quando parcial.
- **Evidências:** `backend/services/cmv_snapshot_service.py:227` e `:246`; `backend/services/inventory_service.py:361`.
- **Validação:** removendo ficha B no probe, permaneceu `[('A', 1.0)]`, portanto a expressão atual indica ausência falsa.
- **Aceite:** aferir completude por componente/opção exigida; não apresentar CMV incompleto como íntegro.

### F16 — P1: disponibilidade não agrega o consumo de todas as linhas do pedido

- **Cenário:** duas linhas consomem o mesmo insumo; cada uma cabe isoladamente no saldo, mas a soma excede o estoque.
- **Causa:** validação por linha consulta o saldo inteiro; baixa grava movimentos sem verificar saldo agregado.
- **Evidências:** `backend/services/order_service.py:594`; `backend/services/inventory_service.py:969`, `:996`, `:334`.
- **Validação:** caminho confirmado no código; não testado com banco nem concorrência real.
- **Aceite:** verificar necessidade total do pedido conforme política de estoque e validar concorrência/transação no PostgreSQL.

## 7. Achados de contratos e integridade

### F17 — P2: atualização permite nulo em campos obrigatórios

- **Causa:** `ProductUpdate` aceita `None` para nome/preço/visibilidade e rota aplica os campos enviados; model tem campos não nulos.
- **Evidências:** `backend/schemas/product.py:140`; `backend/routes/products.py:546`; `backend/models/product.py:26`.
- **Validação:** `ProductUpdate(name=None, price=None, visible_delivery=None)` aceito e serializado com os três nulos. O erro de integridade na gravação não foi reproduzido com banco.
- **Aceite:** distinguir campo omitido, limpeza permitida e nulo proibido antes da persistência.

### F18 — P2: horário impossível de promoção vira ausência de restrição

- **Causa:** regex verifica somente formato; parser retorna `None` para horário impossível.
- **Evidências:** `backend/schemas/product.py:225`; `backend/services/product_pricing_service.py:313`.
- **Validação:** schema aceitou `99:99`/`99:98`; `_parse_time('99:99')` retornou `None`.
- **Aceite:** rejeitar horas/minutos inválidos; validar janela e fuso conforme contrato.

### F19 — P2: categoria/tipo do produto não têm validação relacional suficiente

- **Causa:** categoria/subcategoria são strings aceitas sem validar associação; tipo aceita valor arbitrário. Promoção de subcategoria para raiz via `parent_id:null` é ignorada por `exclude_none=True`.
- **Evidências:** `backend/schemas/product.py:119`; `backend/routes/products.py:532` e `:546`; `backend/services/product_category_service.py:57`.
- **Validação:** schema aceitou nome vazio, tipo `unknown`, categoria inexistente e subcategoria sem vínculo. Comportamento de `parent_id:null` confirmado no código.
- **Aceite:** validar valores e vínculos sem substituir o catálogo existente; permitir remoção explícita de pai quando autorizada pela regra.

### F20 — P2: combinações de promoção não validam referência da opção antes de salvar

- **Causa:** IDs de tamanho/massa são persistidos diretamente, sem conferir produto/tenant/atividade; FKs simples não provam pertencimento ao produto da promoção.
- **Evidências:** `backend/routes/products.py:129`, `:473`, `:481`; `backend/models/product_promotion.py:61`.
- **Impacto:** combinação pode nunca corresponder a seleção válida; referência inexistente depende de erro de banco.
- **Aceite:** validar toda referência no backend e retornar erro de domínio consistente antes da gravação.

## 8. Lacunas e riscos condicionados

### G01 — Cardápio público de salão não é projeção automática do catálogo

`client/pages/salao/SalaoHome.tsx:6`, `:40`, `:54`, `:85` usa HTML estático com overrides CMS; `client/lib/salaoSiteCms.ts:603` e `:614` aplica textos/imagens/blog. Não há consumo do catálogo operacional nessa experiência.

**Conclusão:** mudar um produto no cadastro não garante atualizar o cardápio público do salão. Isso é lacuna de integração se a regra esperada for sincronização; não foi encontrada especificação que obrigue eliminar o conteúdo editorial separado.

### G02 — Conversão de comanda consulta ownership sem filtro explícito

`backend/services/order_service.py:938` e `:1083` consultam `TableSession` por ID sem tenant. O hook em `backend/core/wave6_tenant_orm.py:123` não injeta esse filtro nem cobre essa tabela.

**Limite:** não foi demonstrado vazamento consumado. As FKs compostas em `backend/migrations/versions/20260730_tenant_operations_expand.py:58` podem impedir persistência cruzada e produzir erro de integridade. Falta negação de acesso explícita e teste entre tenants antes de tratar esse limite como seguro.

### G03 — Isolamento está desligado no ambiente local inspecionado

Valores efetivos obtidos de `get_settings()`: `MULTI_TENANT_AUTH_ENABLED`, `TENANT_IDENTITY_CATALOG_ENFORCEMENT_ENABLED`, `TENANT_CUSTOMERS_ORDERS_ENFORCEMENT_ENABLED`, `TENANT_OPERATIONS_ENFORCEMENT_ENABLED`, `MULTI_TENANT_WAVE6_ORM_ENABLED`, `MULTI_TENANT_WAVE7_ORM_ENABLED`, `TENANT_DOMAINS_ENABLED`: todos `False`.

`backend/core/tenant_ownership.py:43` devolve consulta sem filtro quando a flag está desligada. A migration `20260805_tenant_catalog_contract.py:30` exige ownership não nulo; criar com atribuição desabilitada pode falhar em banco com contract aplicado.

**Não extrapolar para produção.** Estado da VPS não consultado. Não habilitar flags apenas para fazer teste passar: exigem compatibilidade de schema, backfill, contexto confiável e provas entre tenants.

### G04 — Cache de produtos não inclui contexto do tenant

`client/context/AppContext.tsx:110` usa chave fixa e TTL de dez minutos. Há risco de catálogo anterior se houver troca de tenant no mesmo origin. Hosts distintos isolam `localStorage`; cenário entre hosts diferentes não deve ser declarado vazamento por essa chave.

### G05 — Totais do carrinho podem ficar desatualizados

Carrinho mantém snapshot local (`client/context/AppContext.tsx:588` e `:895`); checkout envia esses dados (`client/pages/Checkout.tsx:645`). Backend recalcula valores, o que é correto, mas falta prova de comunicação/reconciliação ao usuário quando preço/estoque muda durante a compra.

## 9. Regras que precisam ficar explícitas

1. **Desativar categoria:** hoje não inativa/oculta seus produtos na listagem (`backend/routes/products.py:252`, `:335`). Definir se isso é pretendido antes de alterar.
2. **Múltiplos sabores:** seleção `most_expensive` é substituída por média para divisão maior que 1 (`backend/services/order_service.py:349`; `backend/services/product_pricing_service.py:166`). Confirmar se média é regra fixa atual ou se a configuração deve prevalecer.
3. **Momento da baixa:** opção `auto_consume_on_preparing` também permite consumo em `paid/pago`, inclusive checkout que nasce pago (`backend/services/inventory_service.py:328`; `backend/services/order_service.py:858` e `:1187`). Definir gatilho de negócio único.
4. **CMV operacional e financeiro:** `cmv_service.py:137` inclui pedido em preparação sem pagamento; BI exige pagamento aprovado/pago (`business_intelligence_service.py:327`). A diferença pode ser intencional, mas precisa estar clara na apresentação dos indicadores.
5. **Cancelamento após produção:** estorno de baixa existe (`order_service.py:1189`; `inventory_service.py:393`), mas a política de devolver insumos já produzidos não está comprovada.
6. **Cozinha e canal:** `client/pages/admin/Cozinha.tsx:162` rotula todos os tipos diferentes de retirada como entrega, incluindo salão.

## 10. Pontos preservados e controles encontrados

- Catálogo comercial canônico compartilhado; não é necessário criar um segundo cadastro.
- Produtos inativos são excluídos da listagem pública padrão; brindes possuem filtro próprio.
- Soft delete preserva referência histórica do produto.
- Preços do pedido são recalculados no backend, embora a validação das opções tenha as lacunas descritas.
- Payload público de produto expõe sinal de disponibilidade, sem custos ou saldos internos (`backend/routes/products.py:206`; `backend/schemas/product.py:157`).
- Salão já gera `Order`/`OrderItem` reais e confirma pagamento; seria incorreto afirmar ausência total dessa integração.
- KDS/expedição consomem itens de pedidos, não todo catálogo; BI representa vendas, não produtos meramente cadastrados.
- Baixa e estorno têm verificações de execução anterior e índices únicos por origem/pedido/insumo: migrations `20260627_gestao_inventory_order_sale_deduction.py:19` e `20260627_gestao_inventory_order_sale_reversal.py:19`. Isso não comprova toda a concorrência transacional.
- Produto sem ficha ser comercialmente disponível é comportamento configurável existente; ausência total pode ser indicada como `not_configured`. O defeito específico de composição parcial é F15.

## 11. Validações executadas e limites

### Orquestrador

| Verificação | Resultado |
|---|---|
| `npx.cmd vitest run client --exclude '**/.claude/**'` | 26 arquivos, 123 testes aprovados |
| `npm.cmd run typecheck` | Aprovado, sem erros |
| `npm.cmd run build` | Aprovado: SPA, PWA, servidor e preparação Capacitor |
| Backend: 17 arquivos selecionados | 106 aprovados, 7 ignorados, 3 avisos |
| Migrations/contratos: 6 arquivos selecionados | 14 aprovados, 15 ignorados |
| `python -m alembic -c backend/alembic.ini heads` | Um head: `20261017_runtime_schema` |
| Conexão configurada em transação somente leitura, `SELECT 1` | Falhou com `OperationalError`; sem consulta de dados/migration aplicada |
| Portas locais 5432/8000/3000/5173/8080 | Nenhum listener encontrado no diagnóstico |

Bateria backend principal:

```powershell
python -m pytest tests/test_multitenant_runtime_enforcement.py tests/test_tenant_ownership.py tests/test_tenant_context.py tests/test_tenant_execution.py tests/test_seed_tenant_ownership.py tests/test_rbac_tenant_routes.py tests/test_wave7_inventory_context.py tests/test_wave7_tenant_orm.py tests/test_wave7_finance_context.py tests/test_tenant_background_events.py tests/test_kds_kitchen_dispatch.py tests/test_kds_overview.py tests/test_dispatch_labels.py tests/test_order_board.py tests/test_pagarme_gateway.py tests/test_operation_singleton_compatibility.py tests/test_order_cancellation_migration.py -q -p no:cacheprovider --basetemp=.runtime/pytest-complete-product-audit-20261020
```

Bateria de migrations e contratos:

```powershell
python -m pytest tests/test_alembic_operational_target.py tests/test_initial_schema_migration.py tests/test_tenant_expand_idempotency.py tests/test_runtime_schema_contract.py tests/test_runtime_schema_migration.py tests/test_tenant_customer_order_columns.py -q -p no:cacheprovider --basetemp=.runtime/pytest-product-schema-audit-20261020
```

Os 22 casos ignorados das duas baterias dependem de PostgreSQL de testes explicitamente configurado. Não são testes aprovados. Head do repositório não comprova revision aplicada no banco.

### Agentes

- Backend: 15 testes aprovados de enforcement, ownership e contexto de inventário, com sobreposição à bateria principal.
- Operação: 49 testes aprovados de contexto de inventário, KDS e contratos de marketplace, também com sobreposição. O teste de marketplace cobre código local ainda não rastreado.
- Probes em memória: crash de Product; bootstrap de `/menu`; IDs inválidos com preço-base; schemas nulos/valores arbitrários/horários impossíveis; multiplicadores de receitas e ficha parcial.

Não somar testes sobrepostos para anunciar cobertura maior. Testes existentes aprovados não cobrem todos os defeitos encontrados. Typecheck usa `strictNullChecks:false` (`tsconfig.json`), portanto sua aprovação não impede o crash F01.

Avisos observados: dados Browserslist antigos; opção `inlineDynamicImports` depreciada no build; depreciações Pydantic/FastAPI nos testes. Não bloquearam os comandos.

### Não comprovado nesta auditoria

- Quais produtos estão atualmente cadastrados/visíveis na VPS ou no banco real.
- Fluxo real no navegador entre cliente, administrador, API e PostgreSQL.
- Dados, constraints/backfill e migration efetivamente aplicados.
- Cobrança em provedor, emissão fiscal, impressão física ou conversa real de WhatsApp.
- Concorrência real de vendas, baixa, estorno e criação de pedidos de comanda.
- Operação completa de marketplace ou módulo independente de PDV.

## 12. Plano de correção recomendado e critérios de saída

1. **Autorização e integridade de venda:** F11, F08 e G02; validar negação por papel/tenant e referências inválidas antes de persistir.
2. **Acesso à loja:** F01, F02, F04, F05 e F06; acesso direto sem cache, aliases, erros e canais.
3. **Preço e configuração comercial:** F07, F09, F10, F17–F20; cotação/carrinho/pedido/pagamento coerentes.
4. **Operação do salão:** F12 e F13; opções completas, geração, pagamento e conclusão sem logística indevida.
5. **Estoque e CMV:** F14–F16; regra de frações definida, completude por componente e validação agregada/transacional.
6. **Recuperação e consistência:** F03, cache, conteúdo público do salão e regras da seção 9.
7. **Validação integrada:** banco descartável com schema completo e dois tenants; depois ambiente real autorizado, com evidência de cliente/admin e venda inteira, fracionada, bebida, promoção, brinde, salão, cancelamento e saldo/CMV.

Toda mudança deve preservar API publicada, catálogo canônico, services de negócio, tenant e máquina de estados. Mudança persistida requer migration forward. Alterações estruturais/contratuais exigem avaliação arquitetural antes de implementação.

**Status final:** auditoria local concluída com achados registrados. Correções não executadas. Aprovação da operação completa permanece pendente da resolução dos P1 e validação integrada compatível.
