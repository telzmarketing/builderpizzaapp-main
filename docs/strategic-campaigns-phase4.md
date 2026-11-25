# Campanhas Estratégicas — Fase 4

## Entrega

- A landing pública captura UTM e referrer pelo rastreamento existente.
- Visualização, clique da oferta e rolagem para ofertas são eventos não bloqueantes.
- O carrinho continua sendo o carrinho canônico; a oferta estratégica acompanha a linha como metadado.
- O checkout reenvia `strategic_offer_id` somente quando o carrinho tem uma única linha estratégica, deixando quote, disponibilidade e preço sob autoridade do backend.
- Ofertas de produto entram no carrinho existente; ofertas de kit passam pela tela canônica de combo e preservam o identificador da oferta.
- O indicador de rolagem aparece apenas quando ainda há ofertas abaixo da viewport, desaparece ao alcançar a última oferta e respeita `prefers-reduced-motion`.
- Imagens e vídeo têm fallback silencioso; controles têm rótulos, foco visível e navegação por teclado.

## Gate de preço

A Fase 4 não altera o motor de preço. O backend permanece fail-closed: uma oferta cujo preço promocional não corresponder ao quote canônico do catálogo é rejeitada por `StrategicOfferPriceMismatch`. Isso impede que o preço visual do frontend se torne autoridade e deve ser resolvido em uma fase própria de pricing estratégico antes de liberar descontos divergentes.

## Evidências locais

- `npm.cmd run typecheck` — aprovado.
- `npx.cmd vitest run client/lib/cartKits.spec.ts` — 2 testes aprovados.
- `python -m pytest tests/test_strategic_campaign_phase1.py -q` — 5 testes aprovados.
- `git diff --check` — aprovado.

Não foram executados migration em banco, commit, push ou deploy nesta fase.
