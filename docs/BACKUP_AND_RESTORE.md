# Backup e Restore Telz

Atualizado em: 2026-09-29

Este procedimento cobre os helpers root-owned instalados pelo instalador ou
updater. Backup criado nao equivale a restore comprovado; restaure primeiro em
ambiente descartavel com PostgreSQL 15.

## 1. Criar e validar um conjunto

```bash
sudo /usr/local/bin/backup-telz /opt/telz
sudo readlink -f /var/backups/telz/latest
sudo ls -la /var/backups/telz/latest/
```

Cada conjunto privado em `/var/backups/telz/<ID>/` contem:

- `database.dump`, em formato custom do PostgreSQL;
- `environment.env`, copia protegida para recuperacao manual/forense;
- `uploads.tar.gz` e `baileys.tar.gz`, quando os diretorios existem;
- `SHA256SUMS` e `manifest.json`.

O helper adquire o lock de manutencao, captura o snapshot, valida
`pg_restore --list`, paths dos archives, copia do ambiente e checksums, publica
o conjunto atomicamente e restaura os estados anteriores dos servicos. Ele nao
substitui o `backend/.env` operacional durante o restore normal.

Nao envie dump, `environment.env`, archives ou manifest privado ao Git. Backups
manuais de `.env` devem ficar fora da raiz dos sets, por exemplo em
`/var/backups/telz-manual-env/`.

## 2. Agendamento e retencao

```bash
sudo cat /etc/cron.d/telz-backup
sudo readlink -f /var/backups/telz/latest
sudo ls -la /var/backups/telz/latest/
```

Confirme o timezone real da VPS. O agendamento diario nao comprova execucao,
integridade nem restore. A entrega atual nao deve ser tratada como politica de
retencao: capacidade, expiracao, copia off-site, criptografia e alertas precisam
ser definidos operacionalmente antes da producao.

## 3. Restore destrutivo

O restore exige janela aprovada, acesso de console/SSH alternativo, backup
off-site e identificacao exata do conjunto. Informe o diretorio, nunca um
arquivo isolado:

```bash
sudo /usr/local/sbin/restore-telz \
  /opt/telz \
  /var/backups/telz/<ID>
```

Confirme somente quando o script solicitar:

```text
RESTAURAR <ID>
```

Antes de alterar estado, o helper valida checksums, dump, manifest, archives,
release root-owned e a impressao canonica sem segredo do banco. Divergencia de
release, revision ou identidade do banco bloqueia o restore. Migrar para outro
host, database, usuario ou layout exige um runbook de DR separado.

O helper para writers, cria um safety backup, restaura PostgreSQL, uploads e
Baileys, reinicia e executa health. Em falha tenta recuperar o estado pelo
safety backup. Essa tentativa nao e garantia; se revision ou health nao
convergirem, mantenha os writers parados e preserve:

- conjunto solicitado;
- safety backup informado na saida;
- diretorio com o estado anterior dos arquivos;
- logs de systemd e do helper.

Para instalacoes com usuario, portas, URL publica, diretorios ou helpers nao
padrao, forneca as variaveis `TELZ_*` correspondentes. Nao execute o comando com
defaults e considere o resultado evidencia de um ambiente customizado.

## 4. Rollback de codigo por release

O rollback aceita somente uma release imutavel ja materializada em
`/var/lib/telz/releases/<SHA>/app`, com manifest, digests e compatibilidade de
schema validos:

```bash
sudo /usr/local/sbin/rollback-telz /opt/telz <SHA-COMPLETO>
```

Ele nao faz checkout, build, instalacao de dependencias nem downgrade do banco.
Se o schema atual nao for compativel com a release solicitada, o gate deve
falhar fechado. Nao contorne a allowlist nem altere manifests manualmente;
prefira hotfix forward-only.

## 5. Gate de restore

O gate so pode ser marcado como aprovado quando, em ambiente descartavel com
PostgreSQL 15:

1. um conjunto real for copiado por canal seguro;
2. checksums, manifest e `pg_restore --list` forem aprovados;
3. o restore terminar sem erro;
4. `SELECT 1`, `alembic current` e o health check convergirem;
5. a revision for unica e igual a `20260927_order_board_mvp` para esta entrega;
6. uploads e sessao Baileys forem verificados sem expor segredos;
7. login e fluxos criticos forem testados;
8. duracao, resultado, responsavel e procedimento de retorno forem registrados.

## 6. Estado de prontidao

No checkout local, testes/mocks e inspecao de scripts nao comprovam restore em
PostgreSQL real nem recuperacao na VPS. Permanecem abertos ate evidencia real:

- restore controlado;
- recuperacao pelo safety backup;
- rollback entre releases materializadas compativeis;
- RPO/RTO, retencao, off-site e monitoramento de falhas;
- preservacao do estado original de servicos deliberadamente parados;
- validacao com dois tenants e dados representativos.
