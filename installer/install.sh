#!/usr/bin/env bash
set -Eeuo pipefail

INSTALLER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$INSTALLER_DIR/.." && pwd)"

source "$INSTALLER_DIR/lib/colors.sh"
source "$INSTALLER_DIR/lib/validation.sh"
source "$INSTALLER_DIR/lib/prompts.sh"
source "$INSTALLER_DIR/lib/summary.sh"
source "$INSTALLER_DIR/lib/system.sh"
source "$INSTALLER_DIR/lib/git.sh"
source "$INSTALLER_DIR/lib/database.sh"
source "$INSTALLER_DIR/lib/backend.sh"
source "$INSTALLER_DIR/lib/frontend.sh"
source "$INSTALLER_DIR/lib/systemd.sh"
source "$INSTALLER_DIR/lib/nginx.sh"
source "$INSTALLER_DIR/lib/ssl.sh"
source "$INSTALLER_DIR/lib/firewall.sh"
source "$INSTALLER_DIR/lib/backup.sh"

DEFAULT_CONFIG_FILE="$INSTALLER_DIR/config/defaults.env"
CONFIG_FILE=""
NON_INTERACTIVE=false
RESUME=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config)
      CONFIG_FILE="$2"
      shift 2
      ;;
    --non-interactive)
      NON_INTERACTIVE=true
      shift
      ;;
    --resume)
      RESUME=true
      shift
      ;;
    -h|--help)
      printf 'Uso: sudo bash installer/install.sh [--config arquivo.env] [--non-interactive] [--resume]\n'
      exit 0
      ;;
    *)
      fail "Argumento desconhecido: $1"
      exit 1
      ;;
  esac
done

require_root
cd "$REPO_ROOT"

if [[ -r "$DEFAULT_CONFIG_FILE" ]]; then
  set -a
  source "$DEFAULT_CONFIG_FILE"
  set +a
else
  fail "Arquivo de defaults nao encontrado: $DEFAULT_CONFIG_FILE"
  exit 1
fi
if [[ -n "$CONFIG_FILE" ]]; then
  if [[ -r "$CONFIG_FILE" ]]; then
    set -a
    source "$CONFIG_FILE"
    set +a
  else
    fail "Arquivo de configuracao nao encontrado: $CONFIG_FILE"
    exit 1
  fi
fi
TELZ_NON_INTERACTIVE="$NON_INTERACTIVE"
export TELZ_NON_INTERACTIVE

LOG_DIR=/var/log/telz-installer
STATE_DIR=/var/lib/telz-installer/state
install -d -m 0750 -o root -g root "$LOG_DIR"
install -d -m 0700 -o root -g root "$STATE_DIR"
[[ ! -L "$LOG_DIR" && ! -L "$STATE_DIR" ]] || {
  fail "Diretorios de estado/log do instalador nao podem ser symlinks"
  exit 1
}
LOG_FILE="$LOG_DIR/install-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee -a "$LOG_FILE") 2>&1

phase_done() {
  local marker="$STATE_DIR/$1.done"
  [[ -f "$marker" && ! -L "$marker" && "$(stat -c '%U:%G %a' "$marker")" == "root:root 400" ]]
}
mark_phase() {
  local marker="$STATE_DIR/$1.done"
  local temporary
  temporary="$(mktemp "$STATE_DIR/.phase.XXXXXX")"
  printf 'completed\n' > "$temporary"
  chown root:root "$temporary"
  chmod 0400 "$temporary"
  mv -f -- "$temporary" "$marker"
}
run_phase() {
  local name="$1"
  shift
  if is_true "$RESUME" && phase_done "$name"; then
    ok "Fase ja concluida, pulando: $name"
    return 0
  fi
  info "Iniciando fase: $name"
  "$@"
  mark_phase "$name"
  ok "Fase concluida: $name"
}

collect_answers

validate_required PLATFORM_SLUG
validate_required SERVICE_USER
validate_required INSTALL_DIR
validate_required DATABASE_NAME
validate_required DATABASE_USER
validate_required DATABASE_PASSWORD
validate_required JWT_SECRET_KEY
validate_required ADMIN_EMAIL
validate_required ADMIN_NAME
validate_required ADMIN_PASSWORD
validate_safe_slug "$PLATFORM_SLUG"
validate_install_dir "$INSTALL_DIR"
validate_service_user "$SERVICE_USER"
validate_domain "$PLATFORM_DOMAIN" || {
  fail "PLATFORM_DOMAIN invalido; informe apenas um hostname DNS completo"
  exit 1
}
validate_identifier DATABASE_NAME "$DATABASE_NAME"
validate_identifier DATABASE_USER "$DATABASE_USER"
validate_secret_for_env DATABASE_PASSWORD "$DATABASE_PASSWORD"
validate_secret_for_env JWT_SECRET_KEY "$JWT_SECRET_KEY"
validate_secret_for_env ADMIN_PASSWORD "$ADMIN_PASSWORD"
for port_name in DATABASE_PORT API_PORT WEB_PORT WHATSAPP_GATEWAY_PORT; do
  validate_port "${!port_name:-}" || {
    fail "$port_name deve estar entre 1 e 65535"
    exit 1
  }
done
if [[ "$API_PORT" == "$WEB_PORT" || "$API_PORT" == "$WHATSAPP_GATEWAY_PORT" || "$WEB_PORT" == "$WHATSAPP_GATEWAY_PORT" ]]; then
  fail "API_PORT, WEB_PORT e WHATSAPP_GATEWAY_PORT devem ser distintos"
  exit 1
fi
validate_worker_count "${API_WORKERS:-2}" || {
  fail "API_WORKERS deve estar entre 1 e 64"
  exit 1
}
build_database_url
confirm_plan

run_phase 01_detect_os detect_os
run_phase 02_system_packages install_system_packages
run_phase 03_service_user ensure_service_user
run_phase 04_directories prepare_directories
run_phase 05_firewall configure_firewall
run_phase 06_node install_node_runtime
run_phase 07_code checkout_code
run_phase 07_trusted_assets stage_trusted_installer_assets
load_trusted_installer_assets
run_phase 08_backend install_backend
run_phase 09_env write_backend_env
run_phase 10_database configure_postgresql_local
run_phase 11_alembic run_alembic_gated
run_phase 12_frontend build_frontend
run_phase 13_systemd install_systemd_units
run_phase 14_nginx install_nginx_site
run_phase 15_ssl install_ssl_if_requested
run_phase 16_backup install_backup_cron

info "Executando health check final"
REQUIRE_PUBLIC_HTTPS=false
if is_true "$INSTALL_SSL"; then
  REQUIRE_PUBLIC_HTTPS=true
fi
TELZ_ALEMBIC_TARGET="$ALEMBIC_TARGET" \
  TELZ_REQUIRE_PUBLIC_HTTPS="$REQUIRE_PUBLIC_HTTPS" \
  /usr/local/sbin/telz-health-check "$INSTALL_DIR"
write_summary
ok "Instalacao concluida. Log: $LOG_FILE"
