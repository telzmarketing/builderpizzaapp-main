# Campanhas Estratégicas — Fase 8: Validação Final

## Resultado

Validação local concluída para o fluxo estratégico das Fases 1 a 7.

### Evidências aprovadas

- 12 testes backend focados passaram.
- `python -m compileall -q backend` passou.
- `npm run typecheck -- --pretty false` passou.
- `npm run build` passou para cliente, service worker e servidor.
- `git diff --check` passou.
- Alembic possui um único head: `20261125_strategic_campaign_marketing_phase7`.
- A cadeia estratégica é linear: campanhas, ofertas, visual, comercial e marketing.

## Gate bloqueado

- O banco consultado está em `20261124_finance_projection_queue`, antes das migrations estratégicas.
- A migration não foi aplicada nesta fase.
- O modo offline completo do Alembic falha em migration legada `20261026_customer_phone_lgpd_scope`, que usa `.first()` em resultado offline.
- O trecho incremental também encontra incompatibilidade preexistente de enum PostgreSQL no gerador offline antes de chegar à Fase 7.

Isso exige validação em PostgreSQL de homologação/produção com o executor oficial de migrations antes do deploy. Não é seguro usar `stamp`, alterar `alembic_version` ou executar downgrade manual.

## Aceite da Fase 8

Código e build locais: aprovados.

Banco real, migration aplicada, fluxo autenticado e produção: pendentes para a Fase 9.
