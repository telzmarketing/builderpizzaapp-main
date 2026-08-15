#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

die() {
  echo "[ssl][erro] $*" >&2
  exit 1
}

require_root_owned_executable() {
  local candidate="$1"
  [[ -x "$candidate" && -f "$candidate" && ! -L "$candidate" ]] || die "helper operacional invalido: $candidate"
  [[ "$(stat -c '%U' "$candidate")" == "root" ]] || die "helper deve pertencer a root: $candidate"
  [[ -z "$(find "$candidate" -maxdepth 0 -perm /022 -print -quit)" ]] || \
    die "helper nao pode ser gravavel por grupo/outros: $candidate"
}

[[ "${EUID:-$(id -u)}" -eq 0 ]] || die "execute como root"
SOURCE_SCRIPT="$(realpath -e "$0")"
require_root_owned_executable "$SOURCE_SCRIPT"
[[ "${TELZ_MAINTENANCE_LOCK_HELD:-false}" == "false" ]] || \
  die "finish-ssl nao aceita bypass do lock de manutencao"
MAINTENANCE_LOCK_DIR="/run/lock/telz"
MAINTENANCE_LOCK="$MAINTENANCE_LOCK_DIR/maintenance.lock"
if [[ ! -e "$MAINTENANCE_LOCK_DIR" && ! -L "$MAINTENANCE_LOCK_DIR" ]]; then
  mkdir -m 0700 -- "$MAINTENANCE_LOCK_DIR" || die "nao foi possivel criar diretorio de lock"
fi
[[ -d "$MAINTENANCE_LOCK_DIR" && ! -L "$MAINTENANCE_LOCK_DIR" ]] || die "diretorio de lock inseguro"
[[ "$(realpath -e "$MAINTENANCE_LOCK_DIR")" == "$MAINTENANCE_LOCK_DIR" ]] || die "diretorio de lock indireto"
[[ "$(stat -c '%U:%G:%a' "$MAINTENANCE_LOCK_DIR")" == "root:root:700" ]] || \
  die "diretorio de lock deve ser root:root 0700"
if [[ ! -e "$MAINTENANCE_LOCK" && ! -L "$MAINTENANCE_LOCK" ]]; then
  (set -o noclobber; : > "$MAINTENANCE_LOCK") || die "nao foi possivel criar lock de manutencao"
fi
[[ -f "$MAINTENANCE_LOCK" && ! -L "$MAINTENANCE_LOCK" ]] || die "arquivo de lock inseguro"
[[ "$(stat -c '%U:%G:%a:%h' "$MAINTENANCE_LOCK")" == "root:root:600:1" ]] || \
  die "arquivo de lock deve ser regular root:root 0600 sem hardlinks"
exec 9<>"$MAINTENANCE_LOCK"
flock -n 9 || die "outra manutencao Telz esta em execucao"

DOMAIN="${1:-}"
EMAIL="${2:-}"

[[ "$DOMAIN" =~ ^[a-z0-9]([a-z0-9.-]*[a-z0-9])?$ && "$DOMAIN" == *.* && "$DOMAIN" != *..* ]] || \
  die "uso: telz-finish-ssl app.seudominio.com.br admin@seudominio.com.br"
[[ "$EMAIL" =~ ^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$ ]] || die "email invalido"

if ! command -v certbot >/dev/null 2>&1; then
  apt-get update
  apt-get install -y certbot python3-certbot-nginx
fi

nginx -t
certbot --nginx -d "$DOMAIN" --email "$EMAIL" --agree-tos --non-interactive --redirect
nginx -t
systemctl reload nginx
echo "[ssl] concluido para $DOMAIN"
