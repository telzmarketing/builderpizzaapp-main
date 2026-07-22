# Fundacao de dominios multiempresa

## Decisao arquitetural

O dominio principal continua exclusivo para login, painel administrativo e operacao master. Subdominios e dominios customizados resolvem somente a experiencia publica do tenant. Nao existe fallback para tenant legado ou `default` quando um hostname nao for reconhecido.

## Rollout seguro

- `TENANT_DOMAINS_ENABLED=false` por padrao: nenhum contrato publico atual muda.
- `TENANT_DOMAINS_TRUST_PROXY_HEADERS=false` por padrao.
- `TENANT_DOMAINS_TRUSTED_PROXY_IPS` aceita lista explicita de IPs/CIDRs do proxy.
- `TENANT_DOMAINS_PLATFORM_HOSTNAMES` lista os hostnames reservados do painel/login.

Aceitar `X-Forwarded-Host` exige simultaneamente a flag de proxy e o endereco remoto dentro da allowlist. Caso contrario, somente o Host direto e considerado.

## Ciclo de publicacao

1. `pending`: dominio cadastrado e desafio gerado; somente o hash SHA-256 da prova e persistido.
2. `verified`: prova observada e comparada em tempo constante.
3. `active`: publicacao permitida somente depois de `verified_at` existir.

A resolucao publica exige dominio `active`, tenant `active` e tenant nao removido. O hostname e unico globalmente sem diferenciar maiusculas de minusculas.

## Migration

`20260725_tenant_domains` expande o schema depois de `20260724_tenant_catalog_backfill`. Ela nao foi executada localmente; sua aplicacao e validacao PostgreSQL ficam para o procedimento futuro de instalacao/VPS.
