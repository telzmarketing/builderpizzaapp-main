# Gran Torino — Fase 2: fichas técnicas e composição

**Status:** implementação local concluída e validada; sem commit, push, CI remoto, migration produtiva ou deploy.

## Entrega

Fichas técnicas continuam vinculadas a `products` e às opções comerciais existentes. A nova revisão adiciona instruções, passos ordenados, imagem de referência privada, linhas ordenadas, unidade-base explícita, unidade/quantidade digitadas e fator de conversão congelado, nome comercial autorizado e permissão explícita para retirada. Fichas antigas não recebem unidade, gramatura, imagem ou nome inferidos.

Publicação usa cópia por versão e `expected_version`/`Idempotency-Key`; arquivar não apaga histórico. A composição administrativa é calculada pelo backend compartilhado para preview, CMV e baixa. O resolvedor escolhe a ficha específica aplicável em vez de somar fallback genérico com uma ficha completa específica. Frações de sabores permanecem decimais e o preview distribui o resíduo de arredondamento de forma determinística para que a exibição some ao total consumido.

Remoções e substituições são estruturas explícitas persistidas no pedido/salão. A linha precisa autorizar retirada; substituição exige ficha adicional oficial e opção comercial precificada. Observações livres não alteram estoque. O snapshot CMV guarda `composition_json` quando a composição nova está disponível e o consumo preserva o fallback numérico legado.

Imagens são reprocessadas como PNG raster, mantidas em área privada tenant-owned e servidas apenas por rota autenticada com RBAC. Rotas estáticas/otimizadas públicas recusam o diretório privado, mesmo com o flag legado de uploads ativo. Ingredientes públicos retornam apenas nomes comerciais marcados; quantidades, custos, saldos, lotes e fornecedores permanecem fora do DTO.

## Banco e contratos

A migration `20261021_inventory_recipe_details`, filha de `20261021_inventory_foundation`, adiciona os campos de ficha, FKs tenant-safe de unidades, constraints de conversão/privacidade, `composition_json`, customizações e operações de publicação/arquivamento. Ela é forward-only e não altera migrations históricas. Os targets versionados foram alinhados ao único head atual. A unidade-base de um insumo usado permanece protegida para não reinterpretar fichas históricas.

As rotas novas ficam em `/api/gestao/inventory/v1` para CRUD, preview e ingredientes comerciais, além de `/api/gestao/inventory/recipe-images` para mídia privada. O editor existente de produtos foi evoluído e usa somente `client/lib/api.ts`; não há segundo cadastro comercial.

## Validação local

Foi usado PostgreSQL 15.13 descartável em `127.0.0.1:55432`, com bancos sintéticos separados. A cadeia Alembic do zero passou no head F2; um clone da fase 1 preservou as colunas/dados originais e recebeu a nova revisão. O banco release final confirmou que sete linhas legadas continuam sem conversão inferida ou nome público.

- 84 testes PostgreSQL críticos passaram, sem skips; o gate verificou coleta e aprovação das suítes de fundação, receitas, pedidos e imagens.
- 15 testes de constraints/modelos de detalhes passaram.
- 7 testes de imagem privada passaram em banco PostgreSQL descartável.
- 14 testes do editor React passaram.
- `tests/test_alembic_operational_target.py`: 4 passaram; `git diff --check` passou.
- `python -m compileall -q backend tests` passou.

O typecheck/build completo do frontend foi iniciado, mas o processo `tsc` não encerrou nesta sessão e foi interrompido; portanto não é evidência de aprovação. Não houve validação visual em navegador, CI remoto, dados reais, impressão ou VPS.

## Fora da Fase 2

Não foram ativados consumo por unidade/tentativa, produção/preparação, FEFO, etiquetas, KDS interativo, multioperador, planejamento, OCR, XML ou dashboards CMV. Esses itens permanecem nas fases posteriores do plano.
