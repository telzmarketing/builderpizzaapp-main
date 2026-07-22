#!/usr/bin/env bash

install_backup_cron() {
  if ! is_true "$INSTALL_BACKUP"; then
    info "Backup automatico desabilitado."
    return 0
  fi
  info "Instalando rotina diaria de backup"
  install -m 0755 scripts/backup-telz.sh /usr/local/bin/backup-telz
  cat > /etc/cron.d/telz-backup <<EOF
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
15 3 * * * root /usr/local/bin/backup-telz ${INSTALL_DIR} >/var/log/telz-backup.log 2>&1
EOF
}
