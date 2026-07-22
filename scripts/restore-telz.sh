#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -lt 2 ]]; then
  echo "Uso: sudo bash scripts/restore-telz.sh /opt/telz /var/backups/telz/telz-db-AAAA.dump [uploads.tar.gz]" >&2
  exit 1
fi

INSTALL_DIR="$1"
DB_DUMP="$2"
UPLOADS_ARCHIVE="${3:-}"

if [[ ! -f "$INSTALL_DIR/backend/.env" ]]; then
  echo "[restore][erro] backend/.env nao encontrado" >&2
  exit 1
fi
if [[ ! -f "$DB_DUMP" ]]; then
  echo "[restore][erro] dump nao encontrado: $DB_DUMP" >&2
  exit 1
fi

echo "[restore] Esta operacao pode sobrescrever dados do banco."
read -r -p "Digite RESTAURAR para continuar: " answer
if [[ "$answer" != "RESTAURAR" ]]; then
  echo "[restore] cancelado"
  exit 1
fi

set -a
source "$INSTALL_DIR/backend/.env"
set +a

systemctl stop telz-api telz-web || true
pg_restore --clean --if-exists --no-owner --dbname="$DATABASE_URL" "$DB_DUMP"

if [[ -n "$UPLOADS_ARCHIVE" ]]; then
  if [[ ! -f "$UPLOADS_ARCHIVE" ]]; then
    echo "[restore][erro] arquivo de uploads nao encontrado: $UPLOADS_ARCHIVE" >&2
    exit 1
  fi
  tar -C "$INSTALL_DIR" -xzf "$UPLOADS_ARCHIVE"
fi

systemctl start telz-api telz-web
bash "$INSTALL_DIR/scripts/health-check.sh" "$INSTALL_DIR"
echo "[restore] concluido"
