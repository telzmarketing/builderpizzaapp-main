# SaaS multiempresa - onda 4: pagamentos, webhooks e credenciais

## Escopo comprovado

Esta onda tenantiza somente dados do pagamento de pedidos da loja:

- `payments`: pagamento ligado a `orders`;
- `payment_events`: recepcao e idempotencia de eventos dos gateways de pedidos;
- `payment_provider_customers`: identidade do cliente da loja no gateway;
- `payment_gateway_config`: roteamento e credenciais dos gateways que recebem pagamentos de pedidos.

Billing SaaS (assinatura, plano, fatura e cobranca da plataforma contra o tenant) nao usa essas tabelas e permanece fora deste dominio. Credenciais e webhooks de billing SaaS nao podem reutilizar rotas, configuracoes ou eventos de pagamentos de pedidos.

## Migrations expand/backfill

O head anterior da cadeia multi-tenant foi confirmado em `20260727_tenant_customers_orders_backfill`. O repositorio ainda possui heads historicos anteriores e independentes; esta onda nao tenta mescla-los nem reescrever seu grafo.

1. `20260728_tenant_payments_expand` adiciona `tenant_id` nullable, sem default, com FK para `tenants` em `NOT VALID`.
2. A mesma migration cria pares unicos `(tenant_id, id)`, indices unicos tenant-scoped e FKs compostas:
   - `payments(tenant_id, order_id)` -> `orders(tenant_id, id)`;
   - `payment_provider_customers(tenant_id, customer_id)` -> `customers(tenant_id, id)`.
3. `20260729_tenant_payments_backfill` faz preflight de duplicidade, singleton de configuracao e ownership antes de atribuir o tenant legado.
4. O downgrade do backfill nao apaga ownership, pois ele passa a ser dado de negocio.

Esta onda nao aplica `NOT NULL`, nao valida constraints e nao remove uniques/FKs legadas. Essas operacoes pertencem a uma futura fase contract, depois de telemetria e verificacao fisica na VPS.

## Contrato seguro para webhooks

As rotas globais atuais (`/webhooks/mercadopago`, `/webhooks/asaas` e a rota legada de pagamentos) sao ambiguas quando mais de um tenant possuir credenciais. O contrato de runtime deve obedecer esta sequencia:

1. identificar o tenant por uma chave opaca de endpoint gerada pelo servidor na URL, ou por um identificador de conta do provedor previamente mapeado para exatamente um tenant;
2. carregar exclusivamente a configuracao daquele tenant;
3. validar assinatura/token com a credencial daquele tenant;
4. localizar `payment_events`, `payments`, `orders` e clientes sempre com o mesmo `tenant_id`;
5. rejeitar antes de mutar estado quando o tenant nao for unico, estiver inativo, a assinatura falhar ou o objeto do provedor pertencer a outro tenant.

Nao sao fontes de autoridade para webhook: `Host`, `X-Forwarded-Host`, tenant enviado no body/query/header pelo provedor, tenant `default`, primeira credencial que validar, varredura de credenciais ou `external_reference` sem comprovacao criptografica/mapeamento previo.

Durante compatibilidade, o endpoint global so pode continuar para o tenant legado quando a feature multi-tenant estiver desabilitada. Com multi-tenant habilitado, evento sem resolucao inequivoca deve falhar fechado e ser auditado, nunca cair silenciosamente no tenant legado.

## Credenciais e singleton legado

`payment_gateway_config.id = 'default'` ainda representa o singleton legado. O indice unico parcial em `tenant_id` prepara um singleton por tenant, mas o backend devera deixar de buscar apenas `id = 'default'` antes de criar configuracoes de novos tenants. A fase de integracao deve:

- consultar por `tenant_id` resolvido;
- gerar IDs globais para novas linhas, preservando a linha `default` do tenant legado;
- impedir fallback para variaveis de ambiente compartilhadas quando multi-tenant estiver habilitado;
- mascarar segredos nas respostas e impedir copia de credenciais entre tenants;
- preferir segredo criptografado/secrets manager antes da ativacao em producao.

## Gates antes do contract

- executar as migrations em copia/restauracao do PostgreSQL;
- confirmar zero duplicidades detectadas pelos preflights;
- validar e depois tornar `tenant_id` obrigatorio em onda separada;
- migrar os services e rotas para consultas tenant-scoped;
- disponibilizar endpoint de webhook nao ambiguo e rotacionar URLs/segredos por tenant;
- testar eventos validos, assinatura invalida, replay e tentativa cruzada entre tenants;
- manter rollback por feature flag sem remover a atribuicao gravada.

## Validacao local desta onda

- grafo Alembic inspecionado estaticamente;
- diff verificado por `git diff --check`;
- nenhuma migration foi executada;
- Python/Alembic/PostgreSQL permanecem para a futura validacao operacional/VPS.

## Runtime aditivo preparado

A integracao runtime usa `TENANT_PAYMENT_WEBHOOKS_ENABLED=false` por padrao. Com a flag desligada, as tres rotas globais legadas preservam o contrato anterior. Com a flag ligada, essas rotas retornam 404 e somente os endpoints abaixo sao aceitos:

- `POST /webhooks/mercadopago/{endpoint_key}`;
- `POST /webhooks/asaas/{endpoint_key}`.

`TENANT_PAYMENT_WEBHOOK_ENDPOINTS` e um catalogo JSON mantido pelo servidor no formato `{"chave-opaca":{"tenant_id":"...","provider":"mercado_pago|asaas"}}`. A chave deve ter pelo menos 24 caracteres e cada par tenant/provider pode ter somente uma chave ativa. Depois da resolucao, o runtime exige tenant ativo e exatamente uma `payment_gateway_config` daquele tenant; assinatura, consulta remota e queries locais usam apenas suas credenciais e seu `tenant_id`.

O catalogo nao aceita `Host`, headers de proxy, `tenant_id` do payload/query/header, `default`, `external_reference` ou tentativa sequencial de credenciais como autoridade. Variaveis globais de credenciais tambem nao participam do endpoint tenantizado.

Providers migrados neste contrato: Mercado Pago e ASAAS. Stripe e PagSeguro ainda nao possuem processamento de webhook implementado no service atual e, portanto, permanecem fora da ativacao multiempresa. A chave deve ser gerada por ferramenta operacional criptograficamente segura e provisionada no gateway; sua geracao/rotacao automatizada pertence ao futuro instalador/operacao da VPS.
