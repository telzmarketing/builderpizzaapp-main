#!/usr/bin/env bash
set -Eeuo pipefail

if [[ "${TELZ_TRUSTED_INSTALLER_RUNNER:-false}" != "true" ]]; then
  for argument in "$@"; do
    if [[ "$argument" == "--resume" ]]; then
      [[ -x /usr/local/sbin/telz-installer-resume && ! -L /usr/local/sbin/telz-installer-resume && \
         "$(stat -c '%U:%G %a' /usr/local/sbin/telz-installer-resume)" == "root:root 500" ]] || {
        echo "[ERRO] Runner root-private ausente; a retomada pelo repositorio e recusada." >&2
        exit 1
      }
      exec /usr/local/sbin/telz-installer-resume "$@"
    fi
  done
fi

INSTALLER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ "${TELZ_TRUSTED_INSTALLER_RUNNER:-false}" == "true" ]]; then
  REPO_ROOT="$(realpath -e "${TELZ_INSTALLER_SOURCE_ROOT:?origem persistida ausente}")"
else
  REPO_ROOT="$(cd "$INSTALLER_DIR/.." && pwd)"
fi

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
  CONFIG_FILE_INPUT="$CONFIG_FILE"
  [[ "$CONFIG_FILE_INPUT" = /* ]] || {
    fail "Arquivo de configuracao deve usar caminho absoluto"
    exit 1
  }
  CONFIG_FILE="$(realpath -e -- "$CONFIG_FILE_INPUT")" || {
    fail "Arquivo de configuracao nao encontrado: $CONFIG_FILE"
    exit 1
  }
  [[ "$CONFIG_FILE" == "$CONFIG_FILE_INPUT" && -f "$CONFIG_FILE" && ! -L "$CONFIG_FILE" && \
     "$(stat -c '%U' "$CONFIG_FILE")" == "root" && \
     -z "$(find "$CONFIG_FILE" -maxdepth 0 -perm /022 -print -quit)" ]] || {
    fail "Arquivo de configuracao deve ser regular, canonico, root-owned e nao gravavel por grupo/outros"
    exit 1
  }
  config_parent="$(dirname -- "$CONFIG_FILE")"
  while [[ "$config_parent" != "/" ]]; do
    [[ -d "$config_parent" && ! -L "$config_parent" && "$(stat -c '%U' "$config_parent")" == "root" && \
       -z "$(find "$config_parent" -maxdepth 0 -perm /022 -print -quit)" ]] || {
      fail "Ancestral inseguro no caminho do arquivo de configuracao: $config_parent"
      exit 1
    }
    config_parent="$(dirname -- "$config_parent")"
  done
  set -a
  source "$CONFIG_FILE"
  set +a
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
INSTALLER_LOCK_DIR=/run/lock/telz-installer
INSTALLER_LOCK_FILE="$INSTALLER_LOCK_DIR/install.lock"
if [[ -e "$INSTALLER_LOCK_DIR" || -L "$INSTALLER_LOCK_DIR" ]]; then
  [[ -d "$INSTALLER_LOCK_DIR" && ! -L "$INSTALLER_LOCK_DIR" && "$(stat -c '%U:%G %a' "$INSTALLER_LOCK_DIR")" == "root:root 700" ]] || {
    fail "Diretorio global de lock do instalador e inseguro"
    exit 1
  }
else
  install -d -m 0700 -o root -g root "$INSTALLER_LOCK_DIR"
fi
[[ -d "$INSTALLER_LOCK_DIR" && ! -L "$INSTALLER_LOCK_DIR" && "$(stat -c '%U:%G %a' "$INSTALLER_LOCK_DIR")" == "root:root 700" ]] || {
  fail "Diretorio global de lock do instalador e inseguro"
  exit 1
}
if [[ -e "$INSTALLER_LOCK_FILE" || -L "$INSTALLER_LOCK_FILE" ]]; then
  [[ -f "$INSTALLER_LOCK_FILE" && ! -L "$INSTALLER_LOCK_FILE" && "$(stat -c '%U:%G:%h' "$INSTALLER_LOCK_FILE")" == "root:root:1" && \
     -z "$(find "$INSTALLER_LOCK_FILE" -maxdepth 0 -perm /022 -print -quit)" ]] || {
    fail "Lock global do instalador e inseguro"
    exit 1
  }
fi
command -v flock >/dev/null 2>&1 || {
  fail "Comando obrigatorio nao encontrado: flock"
  exit 1
}
exec 8>"$INSTALLER_LOCK_FILE"
chown root:root "$INSTALLER_LOCK_FILE"
chmod 0600 "$INSTALLER_LOCK_FILE"
flock -n 8 || {
  fail "Outra execucao do instalador esta em andamento"
  exit 1
}
LOG_FILE="$LOG_DIR/install-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee -a "$LOG_FILE") 2>&1

BACKEND_ENV_STAGING_FILE=""
OPERATION_CONFIG_STAGING_FILE=""
cleanup_installer_temporary_files() {
  if [[ -n "${BACKEND_ENV_STAGING_FILE:-}" ]]; then
    rm -f -- "$BACKEND_ENV_STAGING_FILE" || true
    BACKEND_ENV_STAGING_FILE=""
  fi
  if [[ -n "${OPERATION_CONFIG_STAGING_FILE:-}" ]]; then
    rm -f -- "$OPERATION_CONFIG_STAGING_FILE" || true
    OPERATION_CONFIG_STAGING_FILE=""
  fi
}
trap cleanup_installer_temporary_files EXIT

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
for boolean_name in INSTALL_NGINX INSTALL_SSL INSTALL_BACKUP INSTALL_WHATSAPP_GATEWAY \
  RUN_ALEMBIC RUN_TYPECHECK RUN_TESTS RUN_BUILD MULTI_TENANT_AUTH_ENABLED \
  STARTUP_SCHEMA_BOOTSTRAP_ENABLED TENANT_DOMAINS_ENABLED TENANT_DOMAINS_TRUST_PROXY_HEADERS \
  TENANT_IDENTITY_CATALOG_ENFORCEMENT_ENABLED TENANT_CUSTOMERS_ORDERS_ENFORCEMENT_ENABLED \
  TENANT_OPERATIONS_ENFORCEMENT_ENABLED TENANT_PAYMENT_WEBHOOKS_ENABLED \
  MULTI_TENANT_WAVE6_ORM_ENABLED MULTI_TENANT_WAVE7_ORM_ENABLED TENANT_BACKGROUND_CONTEXT_ENABLED \
  TENANT_UPLOAD_NAMESPACE_ENABLED TENANT_CREDENTIALS_ENABLED PLATFORM_RBAC_ENABLED; do
  normalize_boolean "$boolean_name"
done
if [[ -n "${TELZ_OVERWRITE_ENV:-}" ]]; then
  normalize_boolean TELZ_OVERWRITE_ENV
fi
if is_true "$INSTALL_SSL" && ! is_true "$INSTALL_NGINX"; then
  fail "INSTALL_SSL=true exige INSTALL_NGINX=true"
  exit 1
fi
for gated_flag in STARTUP_SCHEMA_BOOTSTRAP_ENABLED TENANT_OPERATIONS_ENFORCEMENT_ENABLED \
  TENANT_PAYMENT_WEBHOOKS_ENABLED MULTI_TENANT_WAVE6_ORM_ENABLED MULTI_TENANT_WAVE7_ORM_ENABLED \
  TENANT_BACKGROUND_CONTEXT_ENABLED TENANT_UPLOAD_NAMESPACE_ENABLED; do
  if is_true "${!gated_flag}"; then
    fail "$gated_flag deve permanecer false na instalacao inicial; ative somente apos homologacao da wave"
    exit 1
  fi
done
validate_safe_slug "$PLATFORM_SLUG"
validate_install_dir "$INSTALL_DIR"
validate_service_user "$SERVICE_USER"
validate_database_mode "$DATABASE_MODE"
if [[ "$DATABASE_MODE" == "external" ]]; then
  validate_database_host "$DATABASE_HOST"
fi
validate_monitoring_dir "$PLATFORM_MONITORING_SNAPSHOT_DIR"
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
confirm_plan

CONFIG_FINGERPRINT="$({
  for key in PLATFORM_NAME PLATFORM_SLUG PLATFORM_DOMAIN PLATFORM_PUBLIC_IP ADMIN_EMAIL ADMIN_NAME ADMIN_PASSWORD SSL_EMAIL \
    INSTALL_DIR SERVICE_USER GIT_REPOSITORY GIT_BRANCH \
    DATABASE_MODE DATABASE_HOST DATABASE_PORT DATABASE_NAME DATABASE_USER DATABASE_PASSWORD JWT_SECRET_KEY \
    API_PORT WEB_PORT API_WORKERS PAYMENT_PROVIDER PAYMENT_GATEWAY MERCADO_PAGO_PUBLIC_KEY \
    MERCADO_PAGO_ACCESS_TOKEN MERCADO_PAGO_WEBHOOK_SECRET ASAAS_API_KEY ASAAS_WEBHOOK_TOKEN \
    WHATSAPP_GATEWAY_RUNTIME_TOKEN WHATSAPP_GATEWAY_EVENT_TOKEN TELZ_OVERWRITE_ENV \
    INSTALL_NGINX INSTALL_SSL INSTALL_BACKUP INSTALL_WHATSAPP_GATEWAY \
    WHATSAPP_GATEWAY_PORT RUN_ALEMBIC ALEMBIC_TARGET RUN_TYPECHECK RUN_TESTS RUN_BUILD \
    MULTI_TENANT_AUTH_ENABLED TENANT_DOMAINS_ENABLED TENANT_DOMAINS_TRUST_PROXY_HEADERS \
    TENANT_DOMAINS_PLATFORM_HOSTNAMES TENANT_IDENTITY_CATALOG_ENFORCEMENT_ENABLED \
    TENANT_CUSTOMERS_ORDERS_ENFORCEMENT_ENABLED TENANT_OPERATIONS_ENFORCEMENT_ENABLED \
    TENANT_PAYMENT_WEBHOOKS_ENABLED MULTI_TENANT_WAVE6_ORM_ENABLED MULTI_TENANT_WAVE7_ORM_ENABLED \
    TENANT_BACKGROUND_CONTEXT_ENABLED TENANT_UPLOAD_NAMESPACE_ENABLED TENANT_CREDENTIALS_ENABLED \
    PLATFORM_RBAC_ENABLED PLATFORM_MONITORING_SNAPSHOT_DIR; do
    printf '%s=%s\0' "$key" "${!key:-}"
  done
} | sha256sum | awk '{print $1}')"
CONFIG_FINGERPRINT_FILE="$STATE_DIR/config.sha256"
if is_true "$RESUME"; then
  [[ -f "$CONFIG_FINGERPRINT_FILE" && ! -L "$CONFIG_FINGERPRINT_FILE" && \
     "$(stat -c '%U:%G %a' "$CONFIG_FINGERPRINT_FILE")" == "root:root 400" && \
     "$(<"$CONFIG_FINGERPRINT_FILE")" == "$CONFIG_FINGERPRINT" ]] || {
    fail "Configuracao efetiva divergiu da instalacao interrompida; retomada recusada"
    exit 1
  }
else
  fingerprint_temp="$(mktemp "$STATE_DIR/.config.XXXXXX")"
  printf '%s\n' "$CONFIG_FINGERPRINT" > "$fingerprint_temp"
  chown root:root "$fingerprint_temp"
  chmod 0400 "$fingerprint_temp"
  mv -f -- "$fingerprint_temp" "$CONFIG_FINGERPRINT_FILE"
fi

run_phase 01_detect_os detect_os
run_phase 02_system_packages install_system_packages
build_database_url
run_phase 00_trusted_assets stage_trusted_installer_assets
load_trusted_installer_assets
run_phase 03_service_user ensure_service_user
run_phase 04_directories prepare_directories
run_phase 05_firewall configure_firewall
run_phase 06_node install_node_runtime
run_phase 07_code checkout_code
run_phase 08_backend install_backend
run_phase 09_env write_backend_env
run_phase 10_database configure_postgresql_local
run_phase 11_alembic run_alembic_gated
run_phase 12_frontend build_frontend
run_phase 13_operational_config persist_operational_config
run_phase 13_systemd install_systemd_units
run_phase 14_nginx install_nginx_site
run_phase 15_ssl install_ssl_if_requested
run_phase 16_backup install_backup_cron

info "Executando health check final"
REQUIRE_PUBLIC_HTTPS=false
HEALTH_ALEMBIC_TARGET=""
if is_true "$INSTALL_SSL"; then
  REQUIRE_PUBLIC_HTTPS=true
fi
if is_true "$RUN_ALEMBIC"; then
  HEALTH_ALEMBIC_TARGET="$ALEMBIC_TARGET"
fi
TELZ_ALEMBIC_TARGET="$HEALTH_ALEMBIC_TARGET" \
  TELZ_REQUIRE_PUBLIC_HTTPS="$REQUIRE_PUBLIC_HTTPS" \
  TELZ_SERVICE_USER="$SERVICE_USER" \
  TELZ_HEALTH_API_PORT="$API_PORT" \
  TELZ_HEALTH_WEB_PORT="$WEB_PORT" \
  TELZ_MONITORING_DIR="$PLATFORM_MONITORING_SNAPSHOT_DIR" \
  /usr/local/sbin/telz-health-check "$INSTALL_DIR"
# The certificate worker may execute only sealed immutable application releases.
# Promote the freshly built production checkout through the existing release pipeline.
validate_initial_active_release() {
  /usr/bin/python3 -I - "$1" "$ALEMBIC_TARGET" <<'PY'
import json, os, re, stat, sys
from pathlib import Path

sha, revision = sys.argv[1:]
if not re.fullmatch(r'[0-9a-f]{40}', sha):
    raise SystemExit('SHA inicial invalido')
root = Path('/var/lib/telz')
current = root / 'current'
expected = root / 'releases' / sha / 'app'

def trusted(path, directory=False):
    info = path.lstat()
    if (info.st_uid != 0 or info.st_mode & 0o022
            or not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))
            or (not directory and info.st_nlink != 1)):
        raise SystemExit('Release inicial possui arquivo ou diretorio mutavel')
    for parent in path.parents:
        item = parent.lstat()
        if not stat.S_ISDIR(item.st_mode) or item.st_uid != 0 or item.st_mode & 0o022:
            raise SystemExit('Parent da release inicial nao e confiavel')
    return info

trusted(root, directory=True)
link = current.lstat()
if not stat.S_ISLNK(link.st_mode) or link.st_uid != 0 or link.st_nlink != 1:
    raise SystemExit('Current inicial nao e symlink root-owned')
if current.resolve(strict=True) != expected:
    raise SystemExit('Resume nao pode substituir outra release ativa')
trusted(expected, directory=True)
manifest = expected / '.telz-release.json'
trusted(manifest)
with os.fdopen(os.open(manifest, os.O_RDONLY | os.O_NOFOLLOW), 'r', encoding='utf-8') as stream:
    opened = os.fstat(stream.fileno())
    visible = manifest.lstat()
    if (not stat.S_ISREG(opened.st_mode) or opened.st_uid != 0 or opened.st_mode & 0o022
            or opened.st_nlink != 1 or opened.st_size > 8192
            or (opened.st_dev, opened.st_ino) != (visible.st_dev, visible.st_ino)):
        raise SystemExit('Manifest inicial nao e confiavel')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Manifest com chave duplicada')
            result[key] = value
        return result
    data = json.loads(stream.read(8193), object_pairs_hook=pairs,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Constante invalida')))
if (not isinstance(data, dict) or type(data.get('schema_version')) is not int
        or data.get('schema_version') != 2 or data.get('status') != 'validated'
        or data.get('git_commit') != sha or data.get('alembic_revision') != revision):
    raise SystemExit('Manifest inicial nao corresponde ao SHA e schema validados')
trusted(expected / 'backend/scripts/tenant_domain_ssl_queue.py')
interpreter = expected / '.venv/bin/python'
trusted(interpreter.parent, directory=True)
trusted(interpreter.resolve(strict=True))
PY
}

promote_initial_release() {
  local initial_commit
  if ! is_true "$INSTALL_SSL" || [[ "$PLATFORM_DOMAIN" != "app.telz.com.br" ]] || ! is_true "$RUN_ALEMBIC"; then
    warn "HTTPS das empresas aguarda promocao para release imutavel de producao; instalacao base preservada."
    return 0
  fi
  [[ "$GIT_BRANCH" == "main" ]] || {
    fail "Promocao imutavel inicial exige GIT_BRANCH=main; instalacao base preservada"
    return 1
  }
  initial_commit="$(sudo -u "$SERVICE_USER" -H git -C "$INSTALL_DIR" rev-parse --verify 'HEAD^{commit}')"
  [[ "$initial_commit" =~ ^[0-9a-f]{40}$ ]] || return 1
  if [[ -e /var/lib/telz/current || -L /var/lib/telz/current ]]; then
    is_true "$RESUME" || {
      fail "Instalador inicial nao substitui release ativa; utilize a atualizacao incremental"
      return 1
    }
    validate_initial_active_release "$initial_commit" || return 1
    TELZ_ALEMBIC_TARGET="$ALEMBIC_TARGET" TELZ_REQUIRE_PUBLIC_HTTPS=true \
      TELZ_PUBLIC_HEALTH_URL="https://${PLATFORM_DOMAIN}/health" \
      TELZ_SERVICE_USER="$SERVICE_USER" TELZ_HEALTH_API_PORT="$API_PORT" \
      TELZ_HEALTH_WEB_PORT="$WEB_PORT" TELZ_MONITORING_DIR="$PLATFORM_MONITORING_SNAPSHOT_DIR" \
      /usr/local/sbin/telz-health-check "$INSTALL_DIR" || return 1
    info "Retomando HTTPS da release imutavel inicial ja validada"
    /usr/bin/python3 -I /usr/local/sbin/telz-domain-ssl --bootstrap \
      --service-user "$SERVICE_USER" --install-dir "$INSTALL_DIR" \
      --api-port "$API_PORT" --web-port "$WEB_PORT" \
      --platform-hostnames "$PLATFORM_DOMAIN,${TENANT_DOMAINS_PLATFORM_HOSTNAMES:-}" \
      --public-ips "${PLATFORM_PUBLIC_IP:-}"
    return $?
  fi
  info "Promovendo instalacao validada para release imutavel e preparando HTTPS das empresas"
  TELZ_SERVICE_USER="$SERVICE_USER" TELZ_ALEMBIC_TARGET="$ALEMBIC_TARGET" \
    TELZ_LEGACY_ADOPTION=true \
    TELZ_LEGACY_ADOPTION_CONFIRM="ADOPT_LEGACY $initial_commit $initial_commit" \
    TELZ_LEGACY_ADOPTION_DB_REVISION="$ALEMBIC_TARGET" \
    TELZ_FORWARD_ONLY_CUTOVER=true \
    TELZ_FORWARD_ONLY_CUTOVER_CONFIRM="FORWARD_ONLY $initial_commit" \
    /usr/local/sbin/telz-deploy-from-origin "$initial_commit" "$INSTALL_DIR" || return $?
  # The updater has released its lock. Preserve explicit installer inputs, including NAT.
  /usr/bin/python3 -I /usr/local/sbin/telz-domain-ssl --bootstrap \
    --service-user "$SERVICE_USER" --install-dir "$INSTALL_DIR" \
    --api-port "$API_PORT" --web-port "$WEB_PORT" \
    --platform-hostnames "$PLATFORM_DOMAIN,${TENANT_DOMAINS_PLATFORM_HOSTNAMES:-}" \
    --public-ips "${PLATFORM_PUBLIC_IP:-}"
}
run_phase 17_immutable_release promote_initial_release
write_summary
cleanup_trusted_installer_assets
ok "Instalacao concluida. Log: $LOG_FILE"
