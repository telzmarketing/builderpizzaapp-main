# Campanhas Estratégicas — Fase 9: Publicação

## Status

Publicação não promovida nesta execução.

## Gates executados

- Checkout identificado na branch `main`.
- Helper oficial exige checkout sem alterações ou arquivos não rastreados.
- Testes do contrato de deploy por origem/manual: 4 passaram.
- O build local da Fase 8 foi aprovado.
- A revisão Alembic alvo é `20261125_strategic_campaign_marketing_phase7`.

## Bloqueio seguro

O checkout contém alterações e artefatos de várias frentes, incluindo mudanças estratégicas e mudanças não relacionadas. O helper oficial rejeita esse estado para impedir uma release que misture ou perca trabalho.

Não foram executados `git reset`, `git clean`, `git stamp`, alteração manual de `alembic_version`, commit abrangente, push ou deploy parcial.

## Próximo passo autorizado

Preparar um commit/release seletivo contendo somente o escopo validado das Campanhas Estratégicas e suas dependências necessárias, revisar o diff final, publicar esse SHA em `origin/main` e então executar o helper oficial com a revisão Alembic alvo.
