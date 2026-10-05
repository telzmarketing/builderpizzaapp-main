# Atualizacao Telz na VPS

Atualizado em: 2026-10-04

Este procedimento cobre atualizacao incremental de uma instalacao existente em
`/opt/telz`. `installer/install.sh` e exclusivo da primeira instalacao ou de
uma reconstrucao planejada; ele nao deve ser reutilizado como updater.

## 1. Caminho suportado

O caminho operacional suportado e o `workflow_dispatch` de
`.github/workflows/deploy.yml`, operacao `deploy`, no commit exato aprovado.
O workflow:

1. identifica a release ativa na VPS;
2. sela o bundle operacional allowlisted;
3. sela os archives de fonte do commit alvo e do commit anterior;
4. resolve e sela o pacote offline de dependencias;
5. verifica os mesmos artefatos em PostgreSQL 15, Python 3.12, Node 22 e pnpm
   10.14.0;
6. envia os artefatos por SSH com fingerprint configurado;
7. promove os arquivos para staging root-owned e verifica SHA-256;
8. materializa releases imutaveis em `/var/lib/telz/releases/<SHA>/app`;
9. cria backup, aplica a revision explicita, troca `current`, reinicia e executa
   health local e HTTPS publico.

O target canonico desta entrega e:

```text
20261004_tenant_upload_ownership_contract
```

O deploy fica bloqueado se o commit publicado nao possuir exatamente esse unico
head ou se banco, manifest, hashes e artefatos nao convergirem.

A cadeia operacional que deve existir no commit publicado e linear:

```text
20260927_order_board_mvp
  -> 20260930_tenant_runtime_uniqueness
  -> 20261003_marketing_workflow_tenant_isolation
  -> 20261003_chatbot_tenant_keys
  -> 20261003_marketing_tenant_keys
  -> 20261003_whatsapp_meta_webhook_tenant_keys
  -> 20261003_email_marketing_tenant_config
  -> 20261003_agente_whatsapp_tenant_foundation
  -> 20261004_wave7_finance_contract
  -> 20261004_wave7_fiscal_contract
  -> 20261004_wave7_management_geocode_contract
  -> 20261004_wave7_logistics_identity_contract
  -> 20261004_tenant_upload_ownership_contract
```

## 2. Preflight

Antes de acionar o workflow, registre sem expor segredos:

```bash
sudo -u telz -H git -C /opt/telz status --short
sudo -u telz -H git -C /opt/telz rev-parse HEAD
sudo readlink -f /var/lib/telz/current
sudo readlink -f /var/backups/telz/latest
sudo systemctl --no-pager --full status \
  telz-api telz-web telz-whatsapp-gateway telz-monitoring.timer
```

O checkout deve estar limpo. Preserve `backend/.env`, `uploads/`, certificados,
backups e `.runtime/baileys`; nao use `reset --hard`, `safe.directory` global ou
movimentacao manual para contornar o gate.

Confirme no commit alvo:

- unico head Alembic `20261004_tenant_upload_ownership_contract`;
- workflow e updater usando o mesmo target;
- CI verde para o mesmo SHA, incluindo o upgrade Alembic em PostgreSQL
  descartavel; CI verde nao substitui o backup nem a migration na VPS;
- commit anterior ancestral do commit alvo;
- secrets `VPS_HOST`, `VPS_USER` (atualmente `root`), `VPS_PORT`,
  `VPS_SSH_KEY`, `VPS_KNOWN_HOSTS` e `VPS_HOST_FINGERPRINT`;
- protecoes/aprovadores do environment `production`;
- URL publica canonica `https://erp.telz.com.br/health` operacional.

`VPS_KNOWN_HOSTS` deve conter a linha completa no formato `known_hosts` para
`VPS_HOST:VPS_PORT`; ele e usado pelas etapas SSH com
`StrictHostKeyChecking=yes`. Nao o substitua pelo fingerprint. Cole-o no secret
somente depois de conferir a chave publica/fingerprint do host por canal
independente e confiavel; nunca aceite uma chave apresentada durante um deploy.

Antes da janela, confirme tambem que o backup recente pode ser lido e que o
procedimento de restore foi ensaiado fora de producao. O updater cria um backup
coerente antes de migrar, mas nao transforma um backup novo em restore provado.

## 3. Comandos manuais que nao sao suportados

Nao copie o updater do checkout e nao execute somente:

```text
sudo /usr/local/sbin/update-telz /opt/telz
```

Esse comando e inexequivel isoladamente por desenho. O updater exige, no mesmo
deploy, todos estes inputs promovidos e root-owned:

- `TELZ_EXPECTED_COMMIT` e `TELZ_PREVIOUS_COMMIT` completos;
- `TELZ_OPERATION_BUNDLE_DIR` com a allowlist exata;
- archive de fonte alvo e seu `TELZ_SOURCE_ARCHIVE_SHA256`;
- archive de fonte anterior e seu `TELZ_PREVIOUS_SOURCE_ARCHIVE_SHA256`;
- archive offline de dependencias e seu `TELZ_DEPENDENCY_ARCHIVE_SHA256`;
- `TELZ_ALEMBIC_TARGET=20261004_tenant_upload_ownership_contract`;
- `TELZ_PUBLIC_HEALTH_URL` quando HTTPS publico e obrigatorio.

Gerar esses valores manualmente, copiar arquivos do worktree ou omitir hashes
remove a cadeia de promocao/verificacao e nao constitui procedimento aprovado.
Se o workflow estiver indisponivel, o deploy deve permanecer bloqueado ate a
cadeia de artefatos ser restaurada; nao use o instalador como fallback.

## 4. Falha, recuperacao e rollback

Antes da janela de manutencao, o updater valida releases alvo/anterior,
compatibilidade de schema e backup. Em falha ele tenta restaurar release ativa,
helpers/units, checkout e estado anterior dos servicos.

Nao existe downgrade automatico de banco. Se a migration ja foi aplicada:

- preserve logs, backup e release ativa;
- mantenha writers parados se o health/recuperacao nao convergir;
- prefira hotfix forward-only compativel com o schema atual;
- use restore somente com janela aprovada e o procedimento de
  `docs/BACKUP_AND_RESTORE.md`.

O rollback por release aceita apenas um SHA completo ja materializado,
root-owned, com manifest/digests validos e schema compativel. Voltar somente o
codigo nao transforma um schema novo em antigo.

## 5. Evidencias de conclusao

Depois de o workflow concluir, registre:

```bash
sudo -u telz -H git -C /opt/telz rev-parse HEAD
sudo readlink -f /var/lib/telz/current
sudo -u telz -H env TELZ_PROJECT_ROOT=/opt/telz bash -lc \
  'cd /var/lib/telz/current && exec .venv/bin/alembic -c backend/alembic.ini current'
sudo systemctl --no-pager --full status \
  telz-api telz-web telz-whatsapp-gateway telz-monitoring.timer
sudo /usr/local/sbin/telz-health-check /opt/telz
```

Confirme que o link `current` termina em `/releases/<SHA-ALVO>/app`, o manifest
registra o mesmo commit e `20261004_tenant_upload_ownership_contract`, e o banco possui uma unica
revision igual ao target.

Tambem valide HTTPS publico, login, loja, pedido, pagamentos, cozinha,
expedicao, WhatsApp, logs e isolamento entre dois tenants. Para o painel TV,
mantenha `ORDER_BOARD_ENABLED=false` e opt-in desativado ate passar HTTPS/cookie,
isolamento A/B e ativacao controlada.

## 6. Gates ainda externos

Um workflow verde comprova a cadeia automatizada daquele run, nao homologacao
geral de producao. Permanecem como evidencias separadas:

- deploy real no host e health HTTPS publico;
- migration em PostgreSQL real com volume/dados de producao representativos;
- teste E2E de cliente e admin;
- isolamento de tenants;
- provedores de pagamento/webhooks reais;
- backup recente e restore controlado;
- rollback para uma release materializada compativel;
- homologacao real das configuracoes nao padrao de usuario, portas e diretorios;
  a propagacao pelo `/etc/telz/operations.conf` e automatizada, mas ainda exige
  teste na VPS.
