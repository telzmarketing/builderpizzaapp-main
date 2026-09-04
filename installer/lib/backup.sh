#!/usr/bin/env bash

install_backup_cron() {
  local backup_source
  if ! is_true "$INSTALL_BACKUP"; then
    info "Backup automatico desabilitado."
    return 0
  fi
  info "Instalando rotina diaria de backup"
  backup_source="$(trusted_installer_asset scripts/backup-telz.sh)"
  install -m 0755 -o root -g root "$backup_source" /usr/local/bin/backup-telz
  cat > /etc/cron.d/telz-backup <<EOF
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
15 3 * * * root /usr/local/bin/backup-telz ${INSTALL_DIR} >/var/log/telz-backup.log 2>&1
EOF
  chmod 0644 /etc/cron.d/telz-backup
}
