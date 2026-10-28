# Atualizacao Telz na VPS

Atualizado em: 2026-10-28

Este procedimento cobre atualizacao incremental de uma instalacao existente em
`/opt/telz`. `installer/install.sh` e exclusivo da primeira instalacao ou de
uma reconstrucao planejada; ele nao deve ser reutilizado como updater.

## Head atual e Gestor IA

O head atual da fonte e `20261028_gestor_gateway_instance`, filho de
`20261028_gestor_multimodal`. A cadeia do Gestor IA adiciona fundacao
administrativa, configuracao, canal Meta, outbox, processamento multimodal e
automacoes proativas tenant-scoped. Nenhum segredo e persistido no banco.
O codigo KDS anterior funciona sobre o schema expandido; o par direcional
`20261027_kds_dispatch_unit_completion:20261027_bi_mobile_analytics_indexes:20261027_logistics_settings_tenant_key:20261028_product_option_groups:20261028_order_item_option_selections:20261028_product_category_capabilities`
foi revisado para rollback apenas de codigo. Outros saltos permanecem bloqueados.
A construcao transacional dos indices pode bloquear escritas nas tabelas;
agende janela operacional para bases grandes e ensaie primeiro em clone.
O downgrade permanece bloqueado.

## Historico: fechamento KDS por unidade

A revision `20261027_kds_dispatch_unit_completion` sucede
`20261026_order_driver_delivery_fee`, que por sua vez sucede
`20261026_product_crust_visibility` e `20261020_inventory_recipe_fractions`.
A migration `20261027_kds_dispatch_unit_completion` adiciona apenas colunas
nullable, uma chave estrangeira e um indice para registrar o fechamento por
unidade. O codigo anterior ignora essas adicoes, portanto o rollback de codigo
para `20261026_order_driver_delivery_fee` preserva o schema expandido. O
downgrade continua bloqueado para preservar o historico de fechamento.

## Historico: fundacao de estoque com Decimal

A revision anterior `20261026_product_crust_visibility` verifica finitude,
amplitude e escala antes de converter quantidades/custos de estoque; residuos
incompativeis bloqueiam a atualizacao em vez de arredondar historico
silenciosamente. Nao ha preenchimento ficticio de lotes, validade ou ownership
legado. Naquela mudanca, codigo antigo desconhecia reservas, lotes e novas
origens de movimento e nao foi aprovada compatibilidade de rollback com a
release anterior. Esse registro historico nao invalida o par direcional agora
revisado para a coluna nullable de repasse; outros pares continuam bloqueados.

Os pares historicos nas secoes seguintes permanecem restritos as respectivas
revisions: nao autorizam salto ou rollback para a nova fundacao.

## Incidente: lacunas restantes de schema e singleton de Gestao

Revision igual ao head e `SELECT 1` nao comprovam compatibilidade de todos os
modulos. O ensaio de todas as migrations com PostgreSQL vazio identificou cinco
colunas adicionais ausentes: `email_templates.category`,
`marketing_automations.trigger_delay_hours` e tres campos de `traffic_campaigns`.
A revision `20261020_inventory_recipe_fractions`, apos `20261017_runtime_schema`, restaura
esse contrato sem substituir dados existentes. O par exato entre essas duas
revisions permite rollback de codigo; downgrade de dados permanece bloqueado.
Tambem foi revisado o par direto
`20261017_site_config:20261020_inventory_recipe_fractions`: uma VPS ainda nessa revision
pode receber o pacote consolidado em um unico deploy, aplicando as duas
migrations aditivas. Isso nao autoriza transitividade geral, outros saltos de
schema nem downgrade; a release anterior conserva acesso ao schema expandido.

A falha `gestao_module_settings_pkey` e um problema diferente: procurar o
singleton legado pelo tenant e tentar cria-lo com o mesmo ID global pode causar
conflito. O reparo de runtime precisa respeitar o contexto confiavel, o registro
ja existente e a concorrencia, sem atribuir configuracoes de outro tenant.

Antes de publicar, o gate de schema deve comparar todas as tabelas e colunas
esperadas pelos models com um PostgreSQL migrado do zero e testar queries reais
de BI e dos singletons operacionais. Tipos JSON/JSONB compativeis e ownership
nullable durante expansao exigem criterio explicito; nao force NOT NULL ou
backfill global para igualar metadados. Na VPS, valide primeiro o SHA ativo,
revision e logs correlacionados ao request_id. Nao ligue bootstrap e nao desligue
isolamento para contornar falhas. O health operacional preserva somente os pares
de schema explicitamente revisados nos scripts de update e rollback.

## Incidente: schema de entregas incompleto

`UndefinedColumn: delivery_persons.password_hash` e
`UndefinedColumn: deliveries.confirmation_code` indicam lacunas do schema de
entregas. A segunda tambem impede o dashboard BI: a contagem existente projeta
os campos do model Delivery. A revision `20261017_delivery_schema`, apos
`20261017_site_config`, restaura os campos esperados preservando dados existentes.
Os campos de autenticacao e documentos dos entregadores permanecem opcionais,
sem senha padrao, preenchimento automatico ou substituicao de valores existentes.

O par exato `20261017_site_config:20261017_delivery_schema` permite rollback
de codigo preservando as colunas aditivas. Nao existe downgrade que apague
credenciais, documentos ou historico de entregas. Atualize pelo fluxo imutavel
com backup e confirme a revision, listagem administrativa de entregadores,
dashboard BI e logs da API. Nao imprima hashes, CPF, CNH, chaves Pix ou codigos
de confirmacao durante a verificacao.

## Incidente: tabela de configuracao ausente

O erro `UndefinedTable: relation "site_config" does not exist` pode ocorrer mesmo
com banco e codigo em `20261014_tenant_domain_ssl`: a tabela esperada pela API
nao fazia parte das migrations. A revision `20261017_site_config` restaura esse
contrato de forma aditiva e preserva configuracoes ja existentes. Nao crie a
tabela manualmente nem habilite bootstrap como alternativa a migration.

O par exato `20261014_tenant_domain_ssl:20261017_site_config` permite rollback
de codigo: a release anterior ja esperava a tabela, que permanece no schema.
Isso nao autoriza downgrade do banco nem libera outros predecessores. Valide
em PostgreSQL descartavel e publique pelo fluxo imutavel com backup; depois
confirme a revision, o registro inicial e `/api/site-config` e o favicon pelo
hostname da loja. A lacuna de Delivery que tambem afeta o BI esta descrita acima.

## Incidente: coluna de cancelamento ausente

O erro `UndefinedColumn: orders.cancelled_by` indica divergencia entre o model
ativo e o schema do banco. A migration `20261014_order_cancellation_tracking`
adiciona os campos de auditoria de cancelamento e preserva registros existentes.
Antes da janela, registre `alembic current` e `alembic heads` usando o ambiente
da release ativa e confirme o backup e o ensaio de restore. Publique a correcao
pelo fluxo incremental abaixo: o updater cria backup antes de aplicar a revision.
Nao execute novamente o instalador, DDL manual ou alteracao de `alembic_version`.

O deploy normal e permitido quando o head da release anterior e exatamente
`20261004_tenant_upload_ownership_contract`: o par com a nova revision foi
revisado para rollback de codigo preservando o schema aditivo e a auditoria.
Outros predecessores continuam bloqueados sem compatibilidade explicita ou
cutover forward-only aprovado. Nao existe downgrade de banco para esta revision.
Depois da atualizacao, confirme a revision aplicada, `/health` e a listagem
autenticada de pedidos, verificando os logs de `telz-api`. Certificado HTTPS
exige validacao separada por hostname.

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

#### Repeticao de deploy e cache

O helper reutiliza o freeze Python de cada release em cache somente depois de
validar os manifests, a fonte Git e a integridade do conteudo selado. Cache
invalido interrompe a operacao; ele nao e substituido por uma nova resolucao.
Releases novas resolvem suas dependencias normalmente. O pacote offline inclui
`python-freezes/<SHA>.txt` para cada commit, e o build usa essas versoes como
constraints. Os downloads de ferramentas, runtime alvo e runtime anterior sao
separados, permitindo versoes diferentes no mesmo wheelhouse.

Ao adotar este formato, atualize primeiro o helper instalado com a copia do
commit alvo, conforme o procedimento abaixo. Nao apague releases nem altere
manifests para contornar divergencias de `python_freeze_sha256`.

Os workflows GitHub selam os pins de cada pacote produzido, mas ainda resolvem
requirements novamente em outra execucao. Ao reutilizar uma release ja presente
na VPS, prefira o helper de origem atualizado: ele consulta o freeze selado local.
Um pacote CI divergente continua sendo rejeitado pelo updater.

Uma release ja selada conserva o digest do artefato usado em seu build original.
Ao reutiliza-la, o updater valida toda a arvore e o cutover, compara por commit os
hashes de requirements, lock e freeze, a configuracao publica e a toolchain. Um
pacote de transporte diferente, por exemplo por conter outro predecessor, nao
reescreve a proveniencia. Mudancas no contrato de build continuam bloqueadas;
builds novos continuam vinculados ao digest exato solicitado.

Helpers anteriores podem conservar o pos-check antigo de igualdade do pacote.
Quando atualizar o proprio helper, instale a copia do mesmo SHA aprovado usando
o procedimento abaixo antes de executar o deploy. Nao apague releases nem edite
manifests para contornar um bloqueio.

#### Disputa transitoria com o timer HTTPS

Se o updater informar outra manutencao em execucao, primeiro consulte `lslocks`,
`fuser`, jobs systemd e logs para identificar o responsavel. Um arquivo de lock
existente nao prova manutencao ativa; nao o apague, nao encerre processos e nao
adquira um lock externo antes do helper. O executor HTTPS compartilha o lock.

Somente quando o timer HTTPS foi confirmado ativo e seus logs identificaram a
atividade concorrente, a janela pode pausa-lo temporariamente. Pare apenas
`telz-domain-ssl.timer`; aguarde o servico concluir naturalmente. Por ser oneshot,
`activating` tambem significa execucao em andamento. Use um subshell com restauracao
obrigatoria e SHA completo aprovado no CI:

```bash
(
  set -Eeuo pipefail
  TARGET='<SHA-ALVO>'
  restore_ssl_timer() {
    rc=$?
    trap - EXIT
    if ! systemctl start telz-domain-ssl.timer; then
      echo 'Falha ao reativar timer HTTPS' >&2
      rc=1
    fi
    exit "$rc"
  }
  trap restore_ssl_timer EXIT
  systemctl stop telz-domain-ssl.timer
  for attempt in $(seq 1 30); do
    state=$(systemctl show telz-domain-ssl.service -p ActiveState --value)
    case "$state" in
      inactive) break ;;
      activating|active|deactivating|reloading) sleep 2 ;;
      *) echo "Servico HTTPS requer diagnostico: $state" >&2; exit 1 ;;
    esac
  done
  test "$(systemctl show telz-domain-ssl.service -p ActiveState --value)" = inactive
  TELZ_ALEMBIC_TARGET=20261028_gestor_gateway_instance \
    /usr/local/sbin/telz-deploy-from-origin "$TARGET" /opt/telz
)
```

Se o servico nao terminar em 60 segundos, o bloco aborta e restaura o timer;
nao interrompe uma emissao real. A pausa nao altera o estado enabled nem dispensa
backup, helper atualizado, CI verde, schema validado e health HTTPS canonico.

#### HTTPS das empresas

Depois de ativar e validar a release, o updater prepara automaticamente o executor
HTTPS, conserva configuracoes root-owned existentes, habilita emissao/renovacao e
publica disponibilidade para o painel. Empresa e Master podem solicitar o certificado
sem executar comandos por dominio. A empresa usa Configuracoes > Dominio e HTTPS.

DNS/TXT corretos e porta 80 publica continuam obrigatorios. Falha da preparacao
mostra aviso no deploy e motivo no painel; health da aplicacao sozinho nao comprova
emissor pronto. VPS sem IP publico local, por exemplo atras de NAT, exige aprovacao
operacional explicita dos destinos. Consulte [o fluxo e os gates](tenant-domain-ssl.md).

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

#### Adocao unica de instalacao legada

Uma VPS que ainda executa diretamente de `/opt/telz`, sem
`/var/lib/telz/current` imutavel, e cujo `HEAD` nao e ancestral do commit alvo,
nao pode usar o comando comum acima. Nao use `pull`, `reset`, `checkout`,
`merge`, `clean` ou `cherry-pick` para tentar normaliza-la.

O helper possui um modo de adocao legada desligado por padrao. Ele so pode ser
usado depois de um ensaio aprovado em clone descartavel do PostgreSQL, backup
validado, health pre-cutover e uma janela de manutencao. O modo exige os tres
valores explicitamente aprovados: SHA legado real, SHA alvo e revision atual do
banco. Ele materializa a fonte legada e o alvo como releases imutaveis, nao
modifica o checkout e exige cutover `forward-only`; uma falha apos a migration
mantem os servicos parados e exige hotfix forward-only ou restauracao explicita
de banco e release.

Nao execute esse modo por tentativa. O procedimento operacional deve ser
gerado para a VPS somente apos registrar o SHA legado, a revision real do banco
e a evidencia do ensaio de restore/migration.

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
20261028_gestor_automations
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
  -> 20261014_order_cancellation_tracking
  -> 20261014_tenant_domain_ssl
  -> 20261017_site_config
  -> 20261017_delivery_schema
  -> 20261026_product_crust_visibility
  -> 20261026_order_driver_delivery_fee
  -> 20261027_kds_dispatch_unit_completion
  -> 20261027_logistics_settings_tenant_key
  -> 20261028_product_category_capabilities
  -> 20261028_gestor_foundation
  -> 20261028_gestor_ai_settings
  -> 20261028_gestor_whatsapp_channel
  -> 20261028_gestor_whatsapp_outbox
  -> 20261028_gestor_multimodal
  -> 20261028_gestor_automations
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

- unico head Alembic `20261028_gestor_gateway_instance`;
- workflow e updater usando o mesmo target;
- CI verde para o mesmo SHA, incluindo o upgrade Alembic em PostgreSQL
  descartavel; CI verde nao substitui o backup nem a migration na VPS;
- commit anterior ancestral do commit alvo;
- para o caminho remoto, secrets `VPS_HOST`, `VPS_USER` (atualmente `root`),
  `VPS_PORT`, `VPS_SSH_KEY`, `VPS_KNOWN_HOSTS` e `VPS_HOST_FINGERPRINT`, mais
  protecoes/aprovadores do environment `production`;
- URL publica canonica `https://app.telz.com.br/health` operacional.

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
- `TELZ_ALEMBIC_TARGET=20261028_gestor_gateway_instance`;
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
registra o mesmo commit e `20261028_gestor_gateway_instance`, e o banco possui uma unica
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
