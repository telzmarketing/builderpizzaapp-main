#!/usr/bin/env bash
set -Eeuo pipefail

INSTALL_DIR="${1:-/opt/telz}"
BACKUP_DIR="${TELZ_BACKUP_DIR:-/var/backups/telz}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

if [[ ! -f "$INSTALL_DIR/backend/.env" ]]; then
  echo "[backup][erro] backend/.env nao encontrado em $INSTALL_DIR" >&2
  exit 1
fi

set -a
source "$INSTALL_DIR/backend/.env"
set +a

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "[backup][erro] DATABASE_URL ausente" >&2
  exit 1
fi

pg_dump --format=custom --file="$BACKUP_DIR/telz-db-$TIMESTAMP.dump" "$DATABASE_URL"

if [[ -d "$INSTALL_DIR/uploads" ]]; then
  tar -C "$INSTALL_DIR" -czf "$BACKUP_DIR/telz-uploads-$TIMESTAMP.tar.gz" uploads
fi

cp "$INSTALL_DIR/backend/.env" "$BACKUP_DIR/telz-env-$TIMESTAMP.env"
chmod 600 "$BACKUP_DIR/telz-env-$TIMESTAMP.env"

echo "[backup] concluido em $BACKUP_DIR"
