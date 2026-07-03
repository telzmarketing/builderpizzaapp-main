# ASAAS Multi Gateway - Execution Plan

Status: Fases 0 a 11 executadas em 2026-07-03.  
Escopo final: multi-gateway implementado no dominio existente `payments`, Mercado Pago preservado, ASAAS Pix habilitado, cartao ASAAS bloqueado por seguranca e documentacao/validacao final registradas.

## 1. Arquitetura atual encontrada

### Frontend

- Aplicacao React 18 + TypeScript + Vite em `client/`.
- Cliente HTTP central em `client/lib/api.ts`; o checkout e o admin ja consomem pagamentos por esse arquivo.
- Checkout principal em `client/pages/Checkout.tsx`.
- Tela administrativa de pagamentos em `client/pages/admin/AdminPagamentos.tsx`.
- Shell administrativo global existe em `client/components/layout/AdminLayout.tsx`, com navegacao em `client/config/adminNavigation.ts` e metadados em `client/config/adminPageMeta.ts`.
- O checkout consulta `paymentsApi.methods()` (`GET /payments/methods`) para habilitar Pix, cartao e pagamento na entrega.
- O checkout cria Pix por `paymentsApi.createPix(order.id, order.total)`, que chama `POST /payments/create` com `payment_method: "pix"` e `formData.payment_method_id: "pix"`.
- O cartao atual carrega `https://sdk.mercadopago.com/js/v2`, cria token via SDK Mercado Pago e envia o token para `paymentsApi.createFromBrick()`.

Observacao importante: o codigo atual nao usa o Payment Brick visual completo do Mercado Pago. Ele usa o SDK `window.MercadoPago` e `createCardToken()` em formulario proprio. A documentacao de negocio pede preservar "Mercado Pago Payment Brick"; portanto a fase de implementacao precisa confirmar se "Brick" aqui significa o fluxo Mercado Pago atual ou se existe regressao documental/historica.

### Backend

- API FastAPI em `backend/`.
- `backend/main.py` inclui os routers sem prefixo e tambem com `/api`, inclusive `payments.router` e `webhooks.router`.
- Dominio de pagamento atual:
  - rota HTTP: `backend/routes/payments.py`;
  - webhook atual Mercado Pago: `backend/routes/webhooks.py`;
  - regra de negocio: `backend/services/payment_service.py`;
  - modelos: `backend/models/payment.py` e `backend/models/payment_config.py`;
  - schemas: `backend/schemas/payment.py` e `backend/schemas/payment_config.py`;
  - migration base do fluxo Mercado Pago: `backend/migrations/versions/20260423_payment_brick.py`.
- `PaymentService` e hoje a fonte de verdade para:
  - criar pagamento Mercado Pago;
  - validar valor contra `order.total`;
  - aplicar status via `payment_sm`;
  - alterar pedido via `order_sm`;
  - consultar Mercado Pago em webhook e polling;
  - publicar `PaymentConfirmed`, `PaymentFailed` e `PaymentReversed`.
- `OrderService.create_from_checkout` tambem cria a linha inicial de `Payment` junto com o pedido: pagamento online nasce hoje com `gateway="mercadopago"` e `provider="mercado_pago"`, enquanto pagamento na entrega nasce como `on_delivery`.
- Efeitos pos-pagamento passam pelo mesmo ponto:
  - consumo/reversao de estoque por `InventoryService`;
  - metricas de cliente por `sync_customer_order_metrics`;
  - eventos internos consumidos por Financeiro, Agente WhatsApp, push e handlers ERP em `backend/main.py`.

### Contratos atuais preservados

- `POST /payments/create`
- `GET /payments/public-key`
- `GET /payments/methods`
- `GET /payments/{order_id}`
- `POST /payments/preference/{order_id}`
- `POST /payments/pay-on-delivery/{order_id}`
- `POST /payments/webhook`
- `POST /webhooks/mercadopago`
- `GET /orders/{order_id}/payment-status`
- `GET /admin/payment-gateway`
- `PUT /admin/payment-gateway`

## 2. Divergencias entre codigo e documentacao

Observacao 2026-07-03: esta secao preserva o retrato encontrado na Fase 0. Os itens implementados ou corrigidos nas fases seguintes estao consolidados na secao 16.

- `KNOWLEDGE_BASE.md` possui secoes historicas com `mock`, Stripe e PagSeguro como gateways; o codigo atual do admin e do service forca Mercado Pago.
- `backend/models/payment_config.py` ainda tem colunas Stripe/PagSeguro e Pix avulso, mas a UI filtra apenas Mercado Pago e o backend sobrescreve `gateway = "mercadopago"`.
- Na Fase 0, `backend/.env.example` ainda declarava `PAYMENT_GATEWAY=mock`, mesmo com `PAYMENT_PROVIDER=mercado_pago` e com o codigo convertendo `mock` para Mercado Pago em producao do fluxo atual.
- `payment_gateway_config` e singleton (`id="default"`) e nao suporta roteamento separado por modalidade.
- `payments` ja tem `provider`, mas ainda nao tem `provider_payment_id` generico; usa `mercado_pago_payment_id` como campo legado principal.
- `payment_events` existe, mas nao possui `provider_event_id`, `provider_payment_id`, `payload_hash`, `processing_status`, indice unico ou deduplicacao forte.
- `PaymentService.process_webhook()` cria `PaymentEvent` com ID aleatorio em toda chamada. A publicacao duplicada de `PaymentConfirmed` tende a ser evitada por `status_changed`, mas o evento externo em si nao e idempotente no banco.
- `payments.amount` usa `Float`; a proposta multi-gateway deveria migrar para `Numeric/Decimal` quando possivel, com transicao segura.
- `payments.order_id` e `unique=True`. O dominio atual representa um pagamento por pedido, nao um historico de multiplas tentativas. Qualquer tentativa de multi-attempt precisa ser decisao explicita, pois impacta contratos e relatorios.
- `OrderService.create_from_checkout` ja grava provider Mercado Pago para pagamento online antes de `POST /payments/create`, entao a resolucao por modalidade precisa atuar tambem nesse ponto ou ser consolidada pelo `PaymentService`.
- O checkout exibe texto fixo "Pagamento 100% seguro via Mercado Pago"; com roteamento ASAAS, esse texto precisa virar neutro ou configuravel.
- A tela `AdminPagamentos.tsx` monta `AdminSidebar` e header proprios, divergindo da regra mais recente do painel que pede shell global em `AdminLayout`.
- Na Fase 0, nao havia ASAAS no codigo (`backend`, `client` ou `.env.example`), alem dos documentos externos fornecidos.

## 3. Arquivos que precisarao ser alterados

### Backend

- `backend/models/payment.py`
- `backend/models/payment_config.py`
- `backend/schemas/payment.py`
- `backend/schemas/payment_config.py`
- `backend/services/payment_service.py`
- Novo arquivo proposto: `backend/services/payment_gateway_resolver.py`
- Novo arquivo proposto: `backend/services/payment_gateways.py` ou pasta `backend/services/payments/`
- Novo arquivo proposto: `backend/services/asaas_client.py`
- Novo arquivo proposto: `backend/services/asaas_gateway.py`
- `backend/routes/payments.py`
- `backend/routes/webhooks.py`
- `backend/routes/admin.py` ou novo router administrativo sob o mesmo dominio `/admin/payment-gateway(s)`
- `backend/config.py`
- `backend/.env.example`
- `backend/main.py` somente para registrar novo router, se necessario, e fallback runtime estritamente compativel.
- `backend/services/order_service.py`
- `setup_database.sql`, pois o bootstrap atual tambem cria `payments` e `payment_gateway_config` sem ASAAS.
- Novas migrations Alembic em `backend/migrations/versions/`.

### Frontend

- `client/lib/api.ts`
- `client/pages/Checkout.tsx`
- Possivel novo componente: `client/components/checkout/AsaasPixPayment.tsx`
- Possivel novo componente futuro: `client/components/checkout/AsaasCardPayment.tsx`
- `client/pages/admin/AdminPagamentos.tsx`
- Se a pagina for realinhada ao shell global: revisar `client/App.tsx`, `client/config/adminNavigation.ts`, `client/config/adminPageMeta.ts` apenas se faltar configuracao de rota/meta.

### Testes e documentacao

- Specs existentes em `client/**/*.spec.ts` se os tipos/helpers mudarem.
- Novos testes backend em estrutura a confirmar, pois hoje a suite local predominante e Node/Vitest.
- `KNOWLEDGE_BASE.md` na fase final, nao nesta Fase 0.
- `docs/ASAAS_MULTI_GATEWAY_EXECUTION_PLAN.md` criado nesta fase.

## 4. Modelo de dados proposto

Preservar `payments` como fonte de verdade. Nao criar tabela concorrente de pagamentos.

### Evolucao de `payments`

Adicionar de forma nullable e compativel:

- `provider_payment_id VARCHAR(160)`
- `provider_customer_id VARCHAR(160)`
- `provider_status VARCHAR(80)`
- `payment_method` apenas se for decidido separar do enum atual `method`; preferencia: manter `method`.
- `currency VARCHAR(3) DEFAULT 'BRL'`
- `installments INTEGER`
- `pix_payload TEXT`
- `pix_qr_code TEXT`
- `pix_expires_at TIMESTAMPTZ`
- `provider_error_code VARCHAR(120)`
- `provider_error_message TEXT`
- `cancelled_at TIMESTAMPTZ`
- `refunded_at TIMESTAMPTZ`

Compatibilidade:

- manter `mercado_pago_payment_id`;
- backfill: `provider='mercado_pago'` e `provider_payment_id = mercado_pago_payment_id` quando aplicavel;
- durante a transicao, escrever ambos para Mercado Pago;
- leitura historica deve aceitar `provider_payment_id` e fallback para `mercado_pago_payment_id`.

### Evolucao de `payment_gateway_config`

Opcoes:

1. Evoluir singleton existente para multi-provider com JSON/colunas por provedor.
2. Criar tabela nova `payment_gateway_provider_configs` para credenciais/capacidades por provedor e manter `payment_gateway_config` como compatibilidade.

Proposta mais clara para longo prazo:

- `payment_gateway_provider_configs`
  - `id`
  - `provider`
  - `enabled`
  - `environment`
  - `credentials_json` ou colunas secretas por provedor, idealmente criptografadas
  - `pix_enabled`
  - `credit_card_enabled`
  - `max_installments`
  - `public_settings_json`
  - `tokenization_status`
  - `last_health_check_at`
  - `last_health_check_status`
  - `last_health_check_message`
  - `created_at`
  - `updated_at`

- `payment_method_routing`
  - `id`
  - `payment_method`
  - `provider`
  - `enabled`
  - `updated_by`
  - `created_at`
  - `updated_at`
  - `UNIQUE(payment_method)`

Alternativa conservadora se o Arquiteto preferir menor mudanca: adicionar `pix_provider`, `credit_card_provider`, `asaas_*` e flags por provedor diretamente em `payment_gateway_config`. Essa alternativa e mais rapida, mas aumenta acoplamento e fica pior se novos provedores entrarem.

### Clientes externos

Criar tabela:

- `payment_provider_customers`
  - `id`
  - `customer_id`
  - `provider`
  - `provider_customer_id`
  - `external_reference`
  - `raw_response_sanitized`
  - `created_at`
  - `updated_at`
  - `UNIQUE(customer_id, provider)`

Regra: nao criar cliente ASAAS novo a cada pedido.

### Evolucao de `payment_events`

Adicionar:

- `provider_event_id VARCHAR(200)`
- `provider_payment_id VARCHAR(160)`
- `payload_hash VARCHAR(64)`
- `processing_status VARCHAR(30) DEFAULT 'received'`
- `error_message TEXT`
- `updated_at TIMESTAMPTZ`

Indices:

- unico parcial por `(provider, provider_event_id)` quando `provider_event_id IS NOT NULL`;
- unico parcial por `(provider, payload_hash)` quando `provider_event_id IS NULL AND payload_hash IS NOT NULL`;
- indice por `(provider, provider_payment_id)`.

## 5. Estrategia de compatibilidade com Mercado Pago

- Preservar `POST /payments/create` como entrada unificada.
- Preservar `GET /payments/public-key` enquanto o checkout Mercado Pago depender dele.
- Adicionar novo `GET /payments/config/public` sem remover `/payments/methods`.
- Mercado Pago continua sendo provider historico para pagamentos antigos.
- Operacoes de consulta, cancelamento e estorno devem resolver pelo provider salvo em `payments.provider`, nunca pela configuracao atual.
- `mercado_pago_payment_id` nao deve ser removido nesta entrega.
- `X-Idempotency-Key` deve continuar no cliente HTTP Mercado Pago.
- Webhooks legados `POST /payments/webhook` e `POST /webhooks/mercadopago` devem continuar ativos.
- A adaptacao para gateway comum deve envolver o minimo possivel do fluxo Mercado Pago atual.

## 6. Fluxo ASAAS Pix

Base validada na documentacao oficial ASAAS em 2026-07-02:

- criar cobranca Pix com `POST /v3/payments`, `billingType: "PIX"`;
- obter QR Code em `GET /v3/payments/{id}/pixQrCode`;
- resposta do QR Code inclui `encodedImage`, `payload` e `expirationDate`;
- QR Code dinamico pode exigir nova obtencao apos atualizacao da cobranca.

Fluxo proposto no projeto:

1. Checkout cria pedido pelo fluxo atual.
2. `POST /payments/create` recebe `order_id` e `method: pix`.
3. Backend ignora provider vindo do navegador, se vier.
4. `PaymentGatewayResolver.resolve("pix")` escolhe ASAAS ou Mercado Pago conforme configuracao persistida.
5. Se ASAAS:
   - buscar/criar cliente em `payment_provider_customers`;
   - criar cobranca ASAAS com valor calculado do pedido;
   - usar `external_reference` do pedido;
   - persistir `provider="asaas"`, `provider_payment_id`, status local `pending`, status externo e resposta sanitizada;
   - buscar QR Code e salvar `pix_payload`, `pix_qr_code`, `pix_expires_at`;
   - retornar somente dados publicos normalizados.
6. Checkout exibe QR Code, copia-e-cola, validade, botao copiar e polling via endpoint interno.
7. Webhook ASAAS recebe evento, autentica e persiste evento idempotente.
8. Backend consulta ASAAS antes de confirmar.
9. `PaymentService` aplica status e publica eventos internos uma unica vez.

## 7. Estrategia segura para cartao ASAAS

Regra desta auditoria: cartao ASAAS nao deve ser implementado ate confirmar o fluxo oficial disponivel para a conta.

Achado oficial relevante:

- a documentacao ASAAS possui pagina de tokenizacao e registra que tokenizacao pode retornar erro de permissao e exigir habilitacao do recurso;
- o fluxo hospedado ASAAS para cartao existe, mas o requisito de negocio deste projeto proibe checkout hospedado/link externo como solucao principal.

Estrategia:

- manter cartao Mercado Pago como caminho seguro e funcional;
- implementar ASAAS Pix primeiro;
- manter flag `asaas.credit_card_enabled=false` ou `tokenization_status="unavailable/not_validated"` ate validacao oficial;
- somente habilitar ASAAS cartao se houver tokenizacao client-side oficial ou outro fluxo que impeca PAN/CVV de passar pelo backend;
- nunca salvar PAN, CVV, payload bruto sensivel, logs de cartao ou token sensivel completo;
- se a tokenizacao nao estiver habilitada, o painel deve mostrar bloqueio claro e impedir selecionar ASAAS para cartao.

## 8. Webhook e idempotencia

### Mercado Pago atual

- `POST /webhooks/mercadopago` e `POST /payments/webhook` delegam para `PaymentService.process_webhook()`.
- A assinatura e verificada com `x-signature` e `x-request-id` quando `MERCADO_PAGO_WEBHOOK_SECRET` esta configurado.
- O backend reconsulta Mercado Pago por `/v1/payments/{id}` antes de aplicar status.
- Duplicidade de efeito interno e reduzida por `status_changed`, mas `payment_events` nao deduplica eventos.

### ASAAS proposto

- Novo endpoint: `POST /webhooks/asaas`, tambem exposto via `/api/webhooks/asaas`.
- Validar header `asaas-access-token` com comparacao segura.
- O token deve seguir recomendacao ASAAS: forte, 32 a 255 caracteres, sem espacos e sem ser API key.
- Responder 200 rapidamente apos persistir/encaminhar processamento seguro, para evitar penalizacao da fila de webhooks.
- Persistir evento antes de efeito de negocio.
- Gerar chave idempotente por `event.id` quando presente; fallback com hash normalizado.
- Reconsultar a cobranca ASAAS antes de confirmar pagamento.
- Conferir `provider_payment_id`, `external_reference`, valor e moeda.
- Mapear eventos ASAAS de pagamento:
  - `PAYMENT_CREATED` -> recebido/pendente;
  - `PAYMENT_CONFIRMED` e `PAYMENT_RECEIVED` -> aprovado/recebido conforme regra interna;
  - `PAYMENT_OVERDUE` -> expirado/vencido quando aplicavel;
  - `PAYMENT_DELETED` -> cancelado;
  - `PAYMENT_REFUNDED` e `PAYMENT_PARTIALLY_REFUNDED` -> estorno/reversao;
  - `PAYMENT_CREDIT_CARD_CAPTURE_REFUSED` -> recusado;
  - eventos de chargeback -> `charged_back` se o enum for evoluido, ou status compativel ate migration.

## 9. Alteracoes no painel administrativo

Evoluir `/painel/pagamentos`, nao criar segunda tela.

Alteracoes:

- remover ou ocultar mock/Stripe/PagSeguro da UX operacional, pois nao estao ativos no backend atual;
- adicionar secao "Roteamento":
  - Gateway do Pix: Mercado Pago ou ASAAS;
  - Gateway do cartao: Mercado Pago ou ASAAS;
  - aviso de que a troca vale apenas para novos pagamentos;
  - aviso de que nao ha fallback automatico.
- adicionar secao Mercado Pago:
  - enabled;
  - ambiente;
  - Public Key;
  - Access Token mascarado;
  - Webhook Secret mascarado;
  - Pix/cartao habilitados;
  - maximo de parcelas;
  - URL webhook;
  - testar conexao.
- adicionar secao ASAAS:
  - enabled;
  - ambiente;
  - API Key mascarada;
  - token webhook mascarado;
  - Pix habilitado;
  - cartao habilitado somente se tokenizacao segura estiver validada;
  - status tokenizacao;
  - maximo de parcelas;
  - URL webhook;
  - testar conexao.
- manter chamadas no `client/lib/api.ts`.
- realinhar pagina ao `AdminLayout` se a rota atual ainda estiver montando sidebar/header proprios.

## 10. Alteracoes no checkout

- Consultar novo endpoint publico `GET /payments/config/public`.
- Manter `/payments/methods` durante transicao.
- O frontend pode usar `provider` apenas para renderizar componente, nunca como autoridade de roteamento.
- Pix Mercado Pago: preservar fluxo atual.
- Pix ASAAS:
  - renderizar componente proprio dentro do checkout existente;
  - criar cobranca via `POST /payments/create`;
  - exibir QR Code, copia-e-cola, validade e polling;
  - permitir regerar apenas conforme regra segura de expiracao.
- Cartao Mercado Pago: preservar fluxo atual.
- Cartao ASAAS:
  - renderizar apenas se tokenizacao oficial segura estiver habilitada;
  - caso contrario, mostrar indisponivel no checkout se admin tentar ativar, mas idealmente impedir ativacao no admin.
- Texto fixo "Mercado Pago" no checkout deve virar neutro ou condicional para nao expor/contradizer o provider.

## 11. Migrations

Fase de migration deve ser pequena e reversivel quando possivel:

1. Adicionar campos genericos em `payments`.
2. Backfill `provider_payment_id` a partir de `mercado_pago_payment_id`.
3. Adicionar indices parciais.
4. Criar/evoluir configuracao de provedores e roteamento.
5. Criar `payment_provider_customers`.
6. Evoluir `payment_events`.
7. Atualizar fallback runtime em `backend/main.py` somente se o padrao do projeto exigir compatibilidade temporaria.
8. Downgrade deve remover colunas/tabelas novas quando seguro, sem apagar campos legados Mercado Pago.

Atencao: os heads Alembic recentes incluem varias trilhas de Gestao e WhatsApp Audio. Antes de criar migration, executar `alembic -c backend/alembic.ini heads` e definir `down_revision` correto.

## 12. Testes

### Backend

- Resolver por modalidade.
- Ignorar provider enviado pelo frontend.
- Impedir provider desabilitado.
- Criar pagamento Mercado Pago sem regressao.
- Criar Pix ASAAS com cliente reutilizado.
- Impedir cobranca duplicada por mesma chave idempotente.
- Persistir provider historico.
- Webhook ASAAS com token valido/invalido.
- Webhook duplicado sem efeito duplicado.
- Webhook fora de ordem.
- Valor divergente.
- Referencia divergente.
- Confirmacao publica `PaymentConfirmed` uma unica vez.
- Reversao publica `PaymentReversed` uma unica vez.
- Backfill e downgrade de migrations.

### Frontend

- Checkout com Pix Mercado Pago.
- Checkout com Pix ASAAS.
- Checkout com cartao Mercado Pago.
- Cartao ASAAS indisponivel quando tokenizacao nao validada.
- Configuracao publica indisponivel.
- Polling e expiracao Pix.
- Admin salva credenciais sem reexpor segredo.
- Admin troca Pix e cartao separadamente.
- Admin impede roteamento invalido.

### Validacao local esperada

- `npm.cmd run typecheck`
- `npm.cmd test` isolado
- `npm.cmd run build`
- `git diff --check`

Validacoes Python/Alembic podem depender de ambiente com Python instalado neste host.

## 13. Riscos

- Cartao ASAAS pode exigir habilitacao de tokenizacao e/ou requisitos PCI que ainda nao foram comprovados.
- `payments.order_id unique` limita multiplas tentativas reais por pedido.
- Credenciais hoje sao salvas em texto no banco; multi-gateway aumenta o risco se nao houver criptografia ou secrets manager.
- `Float` para valor monetario pode gerar divergencias em conciliacao.
- `payment_events` atual nao tem idempotencia forte.
- Eventos internos acionam Financeiro, Estoque, WhatsApp e BI; duplicidade aqui causaria efeito operacional real.
- Admin atual diverge do shell global e pode precisar ajuste visual maior do que a integracao de API.
- O checkout atual de cartao usa formulario proprio com token Mercado Pago, nao um Brick visual completo; isso precisa ser decidido antes de "preservar Payment Brick".
- Webhook ASAAS deve responder rapido para nao prejudicar fila, mas o sistema atual processa sincronicamente.
- Configuracao por ambiente sandbox/producao exige cuidado para nao misturar API keys.

## 14. Plano de execucao em fases pequenas

### Fase 0 - Auditoria e plano

- Criar este documento.
- Nao alterar comportamento.

### Fase 1 - Contrato de configuracao

- Definir modelo final entre tabela nova por provedor ou evolucao do singleton.
- Criar migration de configuracao e roteamento.
- Expor leitura administrativa compativel.
- Testar update sem apagar segredo vazio.

### Fase 2 - Resolver multi-gateway

- Criar `PaymentGatewayResolver`.
- Criar contrato normalizado interno.
- Adaptar Mercado Pago ao contrato sem alterar comportamento publico.
- Adicionar `GET /payments/config/public`.

### Fase 3 - Modelo generico de pagamento/eventos

- Adicionar `provider_payment_id`, campos Pix e eventos idempotentes.
- Backfill Mercado Pago.
- Manter leitura/escrita compativel com campos legados.

### Fase 4 - Cliente ASAAS e clientes externos

- Criar cliente HTTP ASAAS isolado.
- Criar/reutilizar cliente ASAAS.
- Sanitizar logs e respostas.
- Testar concorrencia e duplicidade.

### Fase 5 - ASAAS Pix backend

- Criar cobranca Pix.
- Obter QR Code.
- Persistir pagamento pendente.
- Retornar resposta publica normalizada.
- Garantir idempotencia de criacao.

### Fase 6 - Checkout Pix ASAAS

- Renderizar Pix ASAAS dentro do checkout atual.
- Preservar Pix/cartao Mercado Pago.
- Adicionar polling e expiracao por provider.
- Ajustar textos fixos.

### Fase 7 - Webhook ASAAS

- Criar `POST /webhooks/asaas`.
- Validar `asaas-access-token`.
- Persistir evento idempotente.
- Reconsultar cobranca.
- Aplicar status pelo `PaymentService`.

### Fase 8 - Admin multi-gateway

- Evoluir `/painel/pagamentos`.
- Roteamento por modalidade.
- Secoes Mercado Pago e ASAAS.
- Health check sem criar cobranca real.
- Bloqueio de cartao ASAAS sem tokenizacao validada.

### Fase 9 - Cartao ASAAS seguro

- Somente apos validacao oficial da tokenizacao.
- Implementar componente proprio se PAN/CVV nao passarem pelo backend.
- Testar recusa, aprovacao, parcelamento e ausencia de dados sensiveis.

### Fase 10 - Operacao, estorno e conciliacao

- Consulta/cancelamento/estorno pelo provider historico.
- Rotina ou endpoint protegido de conciliacao.
- Observabilidade sem dados sensiveis.

### Fase 11 - Documentacao final e validacao

- Atualizar `KNOWLEDGE_BASE.md`.
- Atualizar `backend/.env.example`.
- Registrar sandbox/producao e webhooks.
- Rodar validacoes completas.

## 15. Fontes oficiais externas consultadas nesta Fase 0

- Asaas API docs index: https://docs.asaas.com/llms.txt
- Pix dynamic QR Code: https://docs.asaas.com/docs/payments-via-pix-or-dynamic-qr-code.md
- Payment events: https://docs.asaas.com/docs/payment-events.md
- Webhook endpoint/security: https://docs.asaas.com/docs/receive-asaas-events-at-your-webhook-endpoint.md
- Authentication/API key handling: https://docs.asaas.com/docs/authentication.md

## 16. Resultado final da execucao em 2026-07-03

### 16.1 Arquitetura final preservada

- O dominio oficial continua sendo `payments`.
- Mercado Pago foi preservado no fluxo atual de Pix/cartao e nas rotas de webhook existentes.
- ASAAS foi integrado como provider adicional do mesmo dominio, sem criar um segundo modulo de pagamentos.
- O checkout, o painel administrativo, os webhooks e as operacoes de conciliacao usam `PaymentService` como ponto central.

### 16.2 Backend implementado

- `PaymentGatewayResolver` seleciona provider por modalidade a partir da configuracao persistida.
- `AsaasClient` isola chamadas HTTP, autenticacao e erros externos.
- `AsaasGateway` normaliza criacao de Pix, consulta, cancelamento e estorno.
- `PaymentService` cria, sincroniza, concilia, cancela e estorna pelo provider historico gravado em `payments.provider`.
- `backend/routes/webhooks.py` recebe eventos ASAAS em `/webhooks/asaas` e `/api/webhooks/asaas` com token proprio.
- `backend/routes/payments.py` expoe configuracao publica, criacao, status, conciliacao, cancelamento e estorno dentro do dominio existente.

### 16.3 Modelo de dados final

- `payment_gateway_configs` guarda credenciais e roteamento por modalidade.
- `payments` recebeu campos genericos de provider, Pix, checkout URL, vencimento, cancelamento e estorno.
- `customers` recebeu `provider_customer_id`, `provider_customer_id_asaas` e `provider_customer_id_mercado_pago`.
- `payment_events` passou a registrar provider/evento/payload para idempotencia de webhook.
- Backfills preservam Mercado Pago como default de compatibilidade.

### 16.4 Checkout e admin

- Checkout consulta `/payments/config/public` e escolhe Pix ASAAS ou Mercado Pago conforme configuracao.
- Pix ASAAS exibe QR Code/copia e cola no fluxo atual do checkout.
- Cartao Mercado Pago permanece como caminho seguro atual.
- Cartao ASAAS fica bloqueado ate tokenizacao client-side oficial e homologada.
- `/painel/pagamentos` configura Mercado Pago e ASAAS, seleciona provider de Pix/cartao e evita reexpor segredo salvo.
- Admin de pedidos mostra provider e permite conciliar, cancelar ou estornar pelo provider historico do pagamento.

### 16.5 Operacao, webhooks e idempotencia

- Webhook Mercado Pago segue preservado.
- Webhook ASAAS valida `asaas-access-token`, registra evento e reconsulta a cobranca antes de aplicar status.
- Operacoes administrativas usam o provider salvo no pagamento, nao a configuracao atual, evitando cancelar/estornar no gateway errado.
- Financeiro, estoque, WhatsApp e BI continuam dependendo dos eventos internos ja existentes apos mudanca de status.

### 16.6 Migrations criadas

- `backend/migrations/versions/20260702_asaas_multi_gateway_config.py`
- `backend/migrations/versions/20260702_asaas_payment_generic_fields.py`
- `backend/migrations/versions/20260702_asaas_provider_customers.py`

### 16.7 Validacoes locais executadas

- `git diff --check`
- `npm.cmd run typecheck`
- `npm.cmd test`
- `npm.cmd run build`

Validacoes Python/Alembic seguem pendentes neste host porque `py` nao possui runtime Python instalado e `python` nao esta disponivel no PATH. Antes de producao, executar `alembic -c backend/alembic.ini heads`, `alembic -c backend/alembic.ini current` e `alembic -c backend/alembic.ini upgrade head` em ambiente Python valido.

### 16.8 Fontes oficiais adicionais consultadas na validacao final

- Create new payment ASAAS: https://docs.asaas.com/reference/create-new-payment
- Retrieve single payment ASAAS: https://docs.asaas.com/reference/retrieve-a-single-payment
- Refund payment ASAAS: https://docs.asaas.com/reference/refund-payment
- Mercado Pago payments update reference: https://www.mercadopago.com.br/developers/en/reference/payments/_payments_id/put
