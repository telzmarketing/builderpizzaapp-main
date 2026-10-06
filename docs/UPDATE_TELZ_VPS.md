# Atualizacao Telz na VPS

Atualizado em: 2026-10-04

Este procedimento cobre atualizacao incremental de uma instalacao existente em
`/opt/telz`. `installer/install.sh` e exclusivo da primeira instalacao ou de
uma reconstrucao planejada; ele nao deve ser reutilizado como updater.

## 1. Caminhos suportados

Existem tres caminhos aprovados. Todos exigem CI verde no commit exato e nunca
autorizam `git pull`, instalador, `alembic upgrade` ou updater isolado.

### 1.1 Deploy remoto pelo GitHub

O `workflow_dispatch` de `.github/workflows/deploy.yml`, operacao `deploy`,
requer que o GitHub tenha acesso SSH verificado a VPS. O workflow:

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

### 1.2 Deploy direto pela VPS com Git SSH

Use este caminho quando a VPS possui uma chave SSH de saida ja autorizada no
GitHub. A VPS busca o commit aprovado, mas nao faz `git pull`: o helper exige
o SHA completo, monta artefatos locais com hash, usa a mesma promocao imutavel
e delega backup, migration, recuperacao e health ao updater endurecido.

#### Comando unico para cada atualizacao

Depois da instalacao unica do helper abaixo, cada atualizacao e exatamente um
comando. Substitua `<SHA-ALVO>` pelo SHA completo do commit ja aprovado no CI:

```bash
sudo /usr/local/sbin/telz-deploy-from-origin <SHA-ALVO> /opt/telz
```

O SHA continua obrigatorio: a VPS nao deve inferir "o ultimo main", pois ela
nao tem como comprovar que esse commit passou no CI nem que foi o commit
revisado para a janela. O helper faz internamente o backup, `fetch`, build
isolado, validacao e aplicacao da migration forward-only, troca atomica da
release, restart e health local/HTTPS. Em qualquer falha, ele interrompe a
promocao; nao use `git pull`, `reset`, `checkout` ou `clean` como atalho.

#### Instalacao unica do helper

Se `/usr/local/sbin/telz-deploy-from-origin` ainda nao existir, instale a copia
root-owned a partir do mesmo commit aprovado antes da primeira atualizacao.
Substitua `<SHA-ALVO>` pelo mesmo SHA completo e execute, como `root`, nesta
ordem:

```bash
TARGET=<SHA-ALVO>
sudo -u telz -H git -C /opt/telz fetch --prune origin main
sudo -u telz -H git -C /opt/telz status --short
sudo -u telz -H git -C /opt/telz cat-file -e "$TARGET^{commit}"
sudo -u telz -H git -C /opt/telz show "$TARGET:scripts/deploy-telz-from-origin.sh" \
  | sudo install -m 0755 -o root -g root /dev/stdin /usr/local/sbin/telz-deploy-from-origin
```

O segundo comando precisa retornar vazio. Se retornar qualquer arquivo, pare:
nao use `reset`, `checkout` ou `clean` para contornar o bloqueio. O helper
tambem recusa SHA que nao seja fast-forward da release ativa ou que nao esteja
em `origin/main`. Ele pode baixar dependencias Python e pnpm da VPS somente
como usuario de build isolado; por isso a VPS precisa ter acesso de saida aos
registries durante a janela.

O helper root-owned e mantido fora do checkout para que uma atualizacao nunca
execute um script mutavel como root. Reinstale-o somente quando a propria
implementacao de `deploy-telz-from-origin.sh` mudar, usando o procedimento
acima e o SHA aprovado; para releases comuns, use apenas o comando unico.

### 1.3 Deploy manual por pacote selado

Quando a VPS nao deve ser acessada pelo GitHub, use
`.github/workflows/prepare-manual-deploy.yml`. Ele nao possui secrets, SSH ou
SCP: valida o commit e produz um unico artifact de 14 dias contendo fonte alvo
e anterior, dependencias offline, bundle operacional e manifesto SHA-256.

1. Na VPS, com os servicos normais e sem revelar configuracoes, registre o SHA
   atual:

   ```bash
   sudo -u telz -H git -C /opt/telz status --short
   sudo -u telz -H git -C /opt/telz rev-parse HEAD
   ```

2. No GitHub, execute **Preparar pacote de deploy manual** no commit aprovado e
   informe esse SHA completo no campo `previous_commit`. Espere os jobs
   `Validar codigo e migration descartavel` e `Gerar pacote manual selado sem
   segredos` ficarem verdes.

3. Baixe e extraia o artifact `telz-manual-deploy-<SHA-ALVO>` no seu computador.
   Confirme que ele contem somente estes cinco arquivos:

   ```text
   operation-bundle.tar.gz
   target-source.tar.gz
   previous-source.tar.gz
   dependency-bundle.tar.gz
   telz-manual-manifest.json
   ```

4. Transfira essa pasta usando a sua propria chave SSH, por exemplo:

   ```bash
   scp -r telz-manual-deploy-<SHA-ALVO> root@SEU_HOST:/root/
   ```

5. Na VPS, promova os arquivos para um diretorio root-only, instale o helper
   diretamente do `target-source.tar.gz` cujo hash esta no manifesto e execute
   o helper. Nao altere o manifesto nem os artefatos entre estes comandos:

   ```bash
   sudo install -d -m 0700 -o root -g root /var/lib/telz/manual/<SHA-ALVO>
   sudo install -m 0400 -o root -g root /root/telz-manual-deploy-<SHA-ALVO>/* /var/lib/telz/manual/<SHA-ALVO>/
   sudo tar -xOzf /var/lib/telz/manual/<SHA-ALVO>/target-source.tar.gz scripts/deploy-telz-artifacts-manually.sh | sudo install -m 0755 -o root -g root /dev/stdin /usr/local/sbin/telz-deploy-artifacts-manually
   sudo /usr/local/sbin/telz-deploy-artifacts-manually /var/lib/telz/manual/<SHA-ALVO> /opt/telz
   ```

O helper exige que todos os arquivos sejam root-owned, que sejam exatamente os
cinco nomes acima, que os SHA-256 coincidam, que o commit ativo corresponda ao
`previous_commit` e que o bundle operacional seja allowlisted. So depois chama
o updater existente, que cria backup, aplica a migration, materializa a release
imutavel e executa health checks.

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
  -> 20261002_marketing_workflow_foundation
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
- para o caminho remoto, secrets `VPS_HOST`, `VPS_USER` (atualmente `root`),
  `VPS_PORT`, `VPS_SSH_KEY`, `VPS_KNOWN_HOSTS` e `VPS_HOST_FINGERPRINT`, mais
  protecoes/aprovadores do environment `production`;
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
Os unicos caminhos manuais aprovados sao o helper de origem da secao 1.2 e o
pacote selado da secao 1.3; nao use o instalador como fallback.

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
