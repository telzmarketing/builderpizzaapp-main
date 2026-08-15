#!/usr/bin/env bash

install_backend() {
  info "Configurando backend Python"
  command -v python3.12 >/dev/null 2>&1 || {
    fail "Python 3.12 obrigatorio para o backend"
    return 1
  }
  [[ "$(python3.12 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')" == "3.12" ]] || {
    fail "python3.12 nao corresponde a Python 3.12"
    return 1
  }
  sudo -u "$SERVICE_USER" bash -lc "cd '$INSTALL_DIR' && python3.12 -m venv .venv"
  [[ "$($INSTALL_DIR/.venv/bin/python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')" == "3.12" ]] || {
    fail "venv do backend nao usa Python 3.12"
    return 1
  }
  sudo -u "$SERVICE_USER" bash -lc "cd '$INSTALL_DIR' && source .venv/bin/activate && pip install --upgrade pip"
  sudo -u "$SERVICE_USER" bash -lc "cd '$INSTALL_DIR' && source .venv/bin/activate && pip install -r backend/requirements.txt"
}

write_backend_env() {
  local env_file="$INSTALL_DIR/backend/.env"
  local env_temp
  [[ ! -L "$env_file" ]] || {
    fail "backend/.env nao pode ser symlink"
    return 1
  }
  if [[ -f "$env_file" ]]; then
    if [[ "${TELZ_OVERWRITE_ENV:-false}" != "true" ]]; then
      warn "backend/.env existente preservado. Defina TELZ_OVERWRITE_ENV=true para sobrescrever com backup."
      return 0
    fi
    install -d -m 0700 -o root -g root /var/backups/telz-manual-env
    local backup_dir
    backup_dir="$(mktemp -d "/var/backups/telz-manual-env/environment-$(date +%Y%m%d-%H%M%S).XXXXXX")"
    chown root:root "$backup_dir"
    chmod 0700 "$backup_dir"
    local backup_file="$backup_dir/environment.env"
    /usr/bin/python3 - "$INSTALL_DIR" "$backup_file" <<'PY'
import os, stat, sys
install_fd = os.open(sys.argv[1], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
backend_fd = os.open("backend", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=install_fd)
source_fd = os.open(".env", os.O_RDONLY | os.O_NOFOLLOW, dir_fd=backend_fd)
target_fd = os.open(sys.argv[2], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
try:
    if not stat.S_ISREG(os.fstat(source_fd).st_mode):
        raise SystemExit("backend/.env nao e arquivo regular")
    while chunk := os.read(source_fd, 1024 * 1024):
        os.write(target_fd, chunk)
    os.fchmod(target_fd, 0o600)
    os.fsync(target_fd)
finally:
    os.close(source_fd)
    os.close(target_fd)
    os.close(backend_fd)
    os.close(install_fd)
PY
    warn "backend/.env existente salvo em backup antes da sobrescrita: $backup_file"
  fi
  umask 077
  install -d -m 0700 -o root -g root /var/lib/telz-installer/env-staging
  env_temp="$(mktemp /var/lib/telz-installer/env-staging/environment.XXXXXX)"
  cat > "$env_temp" <<EOF
DATABASE_URL=${DATABASE_URL}
APP_NAME=${PLATFORM_NAME}
APP_VERSION=1.0.0
DEBUG=false
JWT_SECRET_KEY=${JWT_SECRET_KEY}
ADMIN_EMAIL=${ADMIN_EMAIL}
ADMIN_NAME=${ADMIN_NAME}
ADMIN_PASSWORD=${ADMIN_PASSWORD}
ALLOWED_ORIGINS=["https://${PLATFORM_DOMAIN}","http://${PLATFORM_DOMAIN}"]
PUBLIC_STORE_URL=https://${PLATFORM_DOMAIN}
VITE_PUBLIC_STORE_URL=https://${PLATFORM_DOMAIN}
PAYMENT_PROVIDER=${PAYMENT_PROVIDER:-mock}
PAYMENT_GATEWAY=${PAYMENT_GATEWAY:-mock}
MERCADO_PAGO_ACCESS_TOKEN=${MERCADO_PAGO_ACCESS_TOKEN:-}
MERCADO_PAGO_PUBLIC_KEY=${MERCADO_PAGO_PUBLIC_KEY:-}
MERCADO_PAGO_WEBHOOK_SECRET=${MERCADO_PAGO_WEBHOOK_SECRET:-}
ASAAS_API_KEY=${ASAAS_API_KEY:-}
ASAAS_WEBHOOK_TOKEN=${ASAAS_WEBHOOK_TOKEN:-}
WHATSAPP_GATEWAY_RUNTIME_URL=http://127.0.0.1:${WHATSAPP_GATEWAY_PORT:-3020}
WHATSAPP_GATEWAY_RUNTIME_TOKEN=${WHATSAPP_GATEWAY_RUNTIME_TOKEN:-${JWT_SECRET_KEY}}
WHATSAPP_GATEWAY_RUNTIME_TIMEOUT_SECONDS=8
WHATSAPP_GATEWAY_RUNTIME_DATA_DIR=${INSTALL_DIR}/.runtime/baileys
WHATSAPP_GATEWAY_BACKEND_EVENT_URL=http://127.0.0.1:${API_PORT}/api/whatsapp-gateway/runtime/events
WHATSAPP_GATEWAY_EVENT_TOKEN=${WHATSAPP_GATEWAY_EVENT_TOKEN:-${JWT_SECRET_KEY}}
MULTI_TENANT_AUTH_ENABLED=${MULTI_TENANT_AUTH_ENABLED:-true}
TENANT_DOMAINS_ENABLED=${TENANT_DOMAINS_ENABLED:-true}
TENANT_DOMAINS_TRUST_PROXY_HEADERS=${TENANT_DOMAINS_TRUST_PROXY_HEADERS:-false}
TENANT_DOMAINS_PLATFORM_HOSTNAMES=${TENANT_DOMAINS_PLATFORM_HOSTNAMES:-${PLATFORM_DOMAIN}}
TENANT_IDENTITY_CATALOG_ENFORCEMENT_ENABLED=false
TENANT_CUSTOMERS_ORDERS_ENFORCEMENT_ENABLED=false
TENANT_OPERATIONS_ENFORCEMENT_ENABLED=false
TENANT_PAYMENT_WEBHOOKS_ENABLED=false
MULTI_TENANT_WAVE6_ORM_ENABLED=false
MULTI_TENANT_WAVE7_ORM_ENABLED=false
TENANT_BACKGROUND_CONTEXT_ENABLED=false
TENANT_UPLOAD_NAMESPACE_ENABLED=false
TENANT_CREDENTIALS_ENABLED=false
PLATFORM_RBAC_ENABLED=${PLATFORM_RBAC_ENABLED:-true}
PLATFORM_MONITORING_SNAPSHOT_DIR=${PLATFORM_MONITORING_SNAPSHOT_DIR:-/var/lib/telz/monitoring}
EOF
  chmod 0600 "$env_temp"
  /usr/bin/python3 - "$env_temp" "$INSTALL_DIR" "$SERVICE_USER" <<'PY'
import os, pwd, secrets, stat, sys
source, install_dir, service_user = sys.argv[1:]
account = pwd.getpwnam(service_user)
install_fd = os.open(install_dir, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
backend_fd = os.open("backend", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=install_fd)
opened_backend = os.fstat(backend_fd)
visible_backend = os.stat("backend", dir_fd=install_fd, follow_symlinks=False)
if not stat.S_ISDIR(visible_backend.st_mode) or (opened_backend.st_dev, opened_backend.st_ino) != (visible_backend.st_dev, visible_backend.st_ino):
    raise SystemExit("diretorio backend inseguro")
original = (opened_backend.st_uid, opened_backend.st_gid, stat.S_IMODE(opened_backend.st_mode))
temporary_name = f".env.install.{secrets.token_hex(16)}"
temporary_fd = -1
try:
    os.fchown(backend_fd, 0, 0)
    os.fchmod(backend_fd, 0o755)
    temporary_fd = os.open(
        temporary_name,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        0o600,
        dir_fd=backend_fd,
    )
    with open(source, "rb") as input_file, os.fdopen(temporary_fd, "wb", closefd=True) as output_file:
        temporary_fd = -1
        while chunk := input_file.read(1024 * 1024):
            output_file.write(chunk)
        output_file.flush()
        os.fchmod(output_file.fileno(), 0o600)
        os.fchown(output_file.fileno(), account.pw_uid, account.pw_gid)
        os.fsync(output_file.fileno())
    os.replace(temporary_name, ".env", src_dir_fd=backend_fd, dst_dir_fd=backend_fd)
    os.fsync(backend_fd)
    installed = os.stat(".env", dir_fd=backend_fd, follow_symlinks=False)
    if not stat.S_ISREG(installed.st_mode) or installed.st_uid != account.pw_uid or stat.S_IMODE(installed.st_mode) != 0o600:
        raise SystemExit("backend/.env instalado com metadados invalidos")
    visible_backend = os.stat("backend", dir_fd=install_fd, follow_symlinks=False)
    if (opened_backend.st_dev, opened_backend.st_ino) != (visible_backend.st_dev, visible_backend.st_ino):
        raise SystemExit("diretorio backend sofreu troca concorrente")
finally:
    if temporary_fd >= 0:
        os.close(temporary_fd)
    try:
        os.unlink(temporary_name, dir_fd=backend_fd)
    except FileNotFoundError:
        pass
    os.fchown(backend_fd, original[0], original[1])
    os.fchmod(backend_fd, original[2])
    os.close(backend_fd)
    os.close(install_fd)
PY
  rm -f -- "$env_temp"
}
