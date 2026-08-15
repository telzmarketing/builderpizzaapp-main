# Backup e Restore Telz

Atualizado em: 2026-08-09

Este procedimento preserva PostgreSQL, ambiente da API e os artefatos locais
que nao pertencem ao Git. Backup criado nao equivale a restore validado: o
ensaio de restauracao deve ocorrer fora de producao antes de uma liberacao.

## 1. Criar um backup

Execute a copia root-owned instalada pelo instalador/atualizador:

```bash
sudo /usr/local/bin/backup-telz /opt/telz
```

O script cria um conjunto privado em:

```text
/var/backups/telz/<AAAAMMDD-HHMMSS-PID>/
```

O link `/var/backups/telz/latest` aponta para o conjunto concluido mais
recente. O diretorio e os artefatos ficam sob ownership `root:root`, sem acesso
de grupo ou outros usuarios.

Cada conjunto possui:

- `database.dump`: dump PostgreSQL custom;
- `environment.env`: copia protegida de `backend/.env`;
- `uploads.tar.gz`, quando `uploads/` existe;
- `baileys.tar.gz`, quando `.runtime/baileys/` existe;
- `SHA256SUMS`;
- `manifest.json`, com identificador, commit, revision Alembic e metadados dos
  componentes, sem conteudo de segredo.

Antes de publicar o conjunto, o script:

- rejeita caminhos amplos ou instalacao invalida;
- adquire o lock exclusivo `/run/lock/telz/maintenance.lock`, para os writers,
  captura o snapshot e restaura exatamente os estados anteriores;
- executa `pg_restore --list` no dump;
- valida que cada tar contem somente diretorios e arquivos regulares sob o
  prefixo permitido, sem links ou tipos especiais;
- compara a copia de `backend/.env` com a origem;
- gera e verifica SHA-256 de todos os componentes;
- move o diretorio temporario para o destino apenas depois das validacoes e
  confirma o health local quando os servicos estavam ativos.

Nao envie `environment.env`, dumps, archives ou manifests privados para o Git.
A copia `environment.env` serve para recuperacao manual/forense; o restore
normal nunca substitui o `.env` operacional atual. Arquivos manuais, como
backups avulsos de `.env`, devem ficar fora da raiz de sets, por exemplo em
`/var/backups/telz-manual-env/`.
A Central Master le somente snapshots sanitizados produzidos pelo observador;
ela nao abre os arquivos privados de backup.

## 2. Agendamento

O atualizador instala `/usr/local/bin/backup-telz` como arquivo `root` e cria
`/etc/cron.d/telz-backup`, com execucao diaria as 03:15 no horario configurado
na VPS. Confirme o agendamento e o ultimo conjunto antes de cada deploy:

```bash
sudo cat /etc/cron.d/telz-backup
sudo readlink -f /var/backups/telz/latest
sudo ls -la /var/backups/telz/latest/
```

## 3. Restaurar um conjunto

O restore e destrutivo e requer uma janela aprovada. Informe o diretorio do
conjunto, nao um arquivo isolado:

```bash
sudo /usr/local/sbin/restore-telz \
  /opt/telz \
  /var/backups/telz/<ID>
```

O script exige a confirmacao textual:

```text
RESTAURAR <ID>
```

Antes de alterar estado ele valida checksums, dump, manifest e archives; rejeita
path traversal; exige a release root-owned correspondente e compara apenas uma
impressao canonica sem segredo da identidade do banco (host, porta, database e
usuario). Rotacao de senha ou parametros de conexao nao reintroduz o segredo
antigo nem substitui `backend/.env`.
Depois para `telz-api`, `telz-web` e, quando instalado,
`telz-whatsapp-gateway`; cria o safety backup com os writers parados; restaura
PostgreSQL, uploads e Baileys;
reinicia os servicos e executa o health check.

Qualquer diferenca de release ou identidade canonica do banco bloqueia o
restore. Recuperacao para outro destino/credencial exige um procedimento de DR
explicito, que nao faz parte deste comando.

Se uma etapa falhar, o script tenta recuperar o estado usando o safety backup.
Isso e uma tentativa de rollback, nao garantia de recuperacao automatica.
Se a revisao ou o health da recuperacao falhar, os writers permanecem parados.

## 4. Rollback de codigo por release

O rollback nao executa checkout, build, instalacao de dependencias nem downgrade
de banco. Ele aceita somente uma release imutavel ja validada, confere novamente
seu digest e compatibilidade de schema e troca atomicamente o link `current`:

```bash
sudo /usr/local/sbin/rollback-telz /opt/telz <SHA-COMPLETO>
```

## 5. Ensaio obrigatorio

O gate de restore somente pode ser marcado como concluido quando, em ambiente
descartavel com PostgreSQL 15:

1. um conjunto real for copiado por canal seguro;
2. checksums e manifest forem validados;
3. o restore terminar sem erro;
4. `alembic current`, `SELECT 1` e o health check forem aprovados;
5. uploads e sessao Baileys forem verificados sem expor segredos;
6. o resultado, duracao e responsavel forem registrados.

No checkout local atual esse ensaio e a restauracao na VPS ainda nao foram
executados; portanto o gate permanece aberto.
