# Backup e Restore Telz

## Backup

```bash
sudo bash scripts/backup-telz.sh /opt/telz
```

Saida padrao:

```text
/var/backups/telz/
```

Inclui:

- dump PostgreSQL custom;
- uploads, se existirem;
- copia segura do `backend/.env`.

## Restore

```bash
sudo bash scripts/restore-telz.sh /opt/telz /var/backups/telz/telz-db-AAAA.dump
```

Com uploads:

```bash
sudo bash scripts/restore-telz.sh /opt/telz /var/backups/telz/telz-db-AAAA.dump /var/backups/telz/telz-uploads-AAAA.tar.gz
```

O restore exige confirmacao textual e reinicia os services.
