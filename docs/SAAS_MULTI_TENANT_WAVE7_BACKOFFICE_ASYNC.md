# Onda 7 — Estoque, CMV, financeiro, fiscal, arquivos e processamento assíncrono

## Inventário comprovado

Esta onda foi reconciliada com `backend/models/inventory.py`, `cmv.py`,
`finance.py`, `fiscal.py`, `gestao.py`, `delivery.py`, com as rotas de upload e
com o inventário da auditoria multiempresa.

São tenant-owned 27 tabelas de gestão, estoque, CMV, financeiro e fiscal. Três
tabelas-filhas não tinham ownership explícito: `inventory_purchase_items`,
`inventory_recipe_items` e `fiscal_document_items`.

`geocode_cache` também entra como tenant-owned. Embora seja cache, a linha
persiste o endereço normalizado em `query`; portanto não há prova de que seja
cache global sem PII. Nenhum cache puramente técnico/global foi incluído.

Jobs, outbox e artefatos persistidos do Agente WhatsApp, jobs de IA do cliente e
OAuth state já foram cobertos pela onda 6. Eles não são duplicados aqui. A
propagação de `tenant_id` no payload/worker continua sendo obrigação da camada de
aplicação antes da ativação multiempresa.

## Migrations

### `20260803_tenant_backoffice_async_expand`

- encadeada após `20260802_tenant_marketing_crm_whatsapp_backfill`;
- adiciona quatro colunas `tenant_id` nullable e sem default;
- remove server defaults legados das 24 colunas existentes e preserva nullable;
- cria FK para `tenants` e FKs compostas com `NOT VALID`;
- cria pares únicos `(tenant_id, id)` e cinco uniques tenant-scoped comprovadas;
- mantém FKs escalares e uniques globais durante compatibilidade;
- não aplica `NOT NULL`, não valida constraints e não executa contract.

Relacionamentos escalares com `ON DELETE SET NULL/RESTRICT` recebem FK composta
sem ação de delete. Isso evita que um `SET NULL` composto apague também o
`tenant_id`. Filhos descartáveis preservam `ON DELETE CASCADE`.

### `20260804_tenant_backoffice_async_backfill`

- exige o tenant ativo `tenant-legacy-default`;
- rejeita tenant desconhecido antes de qualquer escrita;
- executa cinco preflights de duplicidade para os cinco índices scoped;
- executa um preflight 1:1 para cada uma das 38 relações compostas;
- normaliza somente `NULL` e o rótulo legado `default`;
- possui downgrade não destrutivo.

## Uploads e arquivos

Os endpoints atuais gravam diretamente em `uploads/<uuid>` e retornam URL
pública. Não existe tabela ORM de metadados que possa ser tenantizada nesta onda.
Também não foi criada uma tabela paralela sem integração, pois isso produziria
uma falsa garantia de isolamento.

Antes do segundo tenant, a aplicação precisa gravar em
`uploads/{tenant_id}/...`, carregar o tenant do contexto validado, persistir
ownership/metadados (hash, MIME, tamanho e visibilidade) no fluxo oficial e
autorizar arquivos privados. Referências existentes, como certificado fiscal e
artefatos do Agente WhatsApp, permanecem ownership da linha que as contém.

## Compatibilidade, gates e riscos

- Os 28 models ORM desta onda agora espelham `tenant_id` nullable, sem default,
  com FK para `tenants` e o par único `(tenant_id, id)`; as cinco uniques
  tenant-scoped também estão declaradas no metadata.
- As 38 FKs compostas permanecem declaradas na migration, sem duplicá-las no
  mapper legado. Declará-las ao lado das FKs escalares atuais tornaria joins de
  `relationship()` ambíguos antes da conversão integral dos relacionamentos.
- `backend/core/wave7_tenant_orm.py` fornece scope de leitura e atribuição de
  ownership apenas com `MULTI_TENANT_WAVE7_ORM_ENABLED=true`; o default é OFF,
  contexto validado é obrigatório e nenhuma rota foi ativada nesta onda.
- A PK global de `geocode_cache` permanece durante expand; a aplicação deve
  consultar/escrever com tenant antes de liberar o segundo tenant.
- Credenciais, certificados e XML fiscal exigem proteção de segredo e arquivos
  privados; ownership no banco não substitui criptografia/autorização.
- Nenhum worker/job pode derivar tenant de contexto HTTP ausente ou de fallback.
- Uploads continuam uma lacuna comprovada: nenhuma tabela de metadados foi
  inventada e o helper desta onda não concede isolamento ao diretório público.
- Contract, `NOT NULL`, `VALIDATE CONSTRAINT` e remoção de uniques globais só
  podem ocorrer depois de preflights físicos, canário A/B e rollback comprovado.

## Validação local

- cadeia estática revisada: `20260802 -> 20260803 -> 20260804`;
- 28 tabelas reconciliadas entre expand e backfill;
- 38 FKs compostas reconciliadas 1:1 com 38 preflights de ownership;
- cinco uniques reconciliadas 1:1 com cinco preflights de duplicidade;
- 28 models reconciliados com 28 FKs de tenant e 28 pares únicos;
- testes unitários do gate/helper adicionados em `tests/test_wave7_tenant_orm.py`;
- `git diff --check` executado nos arquivos desta onda.

Python, Alembic e PostgreSQL não estão disponíveis localmente. As migrations não
foram executadas; `alembic heads/history`, upgrade/downgrade, contagens físicas,
`VALIDATE CONSTRAINT` e query plans permanecem gates do futuro instalador/VPS.
