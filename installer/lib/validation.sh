#!/usr/bin/env bash

is_true() {
  case "${1:-}" in
    true|TRUE|1|yes|YES|sim|SIM) return 0 ;;
    *) return 1 ;;
  esac
}

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    fail "Execute como root: sudo bash installer/install.sh"
    exit 1
  fi
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || {
    fail "Comando obrigatorio nao encontrado: $1"
    exit 1
  }
}

validate_required() {
  local name="$1"
  local value="${!name:-}"
  if [[ -z "$value" ]]; then
    fail "Parametro obrigatorio ausente: $name"
    exit 1
  fi
}

validate_slug() {
  [[ "$1" =~ ^[a-z][a-z0-9-]*$ ]]
}

validate_safe_slug() {
  if ! validate_slug "$1"; then
    fail "PLATFORM_SLUG invalido. Use letras minusculas, numeros e hifen, iniciando com letra."
    exit 1
  fi
}

validate_install_dir() {
  local value="$1"
  case "$value" in
    /opt/*|/home/*) ;;
    *)
      fail "INSTALL_DIR deve ficar em /opt/... ou /home/..."
      exit 1
      ;;
  esac
  if [[ "$value" == "/" || "$value" == "/home" || "$value" == "/opt" ]]; then
    fail "INSTALL_DIR amplo demais: $value"
    exit 1
  fi
}

validate_identifier() {
  local label="$1"
  local value="$2"
  if [[ ! "$value" =~ ^[a-zA-Z_][a-zA-Z0-9_]{1,62}$ ]]; then
    fail "$label invalido. Use letras, numeros e underscore, iniciando com letra/underscore."
    exit 1
  fi
}

validate_secret_for_env() {
  local label="$1"
  local value="$2"
  if [[ "$value" =~ [[:space:]\'\"] ]]; then
    fail "$label contem espaco ou aspas. Use segredo sem espacos/aspas nesta versao do instalador."
    exit 1
  fi
}

validate_domain() {
  local domain="$1"
  [[ -z "$domain" ]] && return 0
  [[ "$domain" != http*://* ]] || return 1
  [[ "$domain" != *"/"* ]] || return 1
  [[ "$domain" != *":"* ]] || return 1
  [[ "$domain" =~ ^[A-Za-z0-9.-]+$ ]]
}

validate_port() {
  [[ "$1" =~ ^[0-9]+$ ]] && [[ "$1" -ge 1 ]] && [[ "$1" -le 65535 ]]
}

mask_value() {
  local key="$1"
  local value="$2"
  case "${key,,}" in
    *password*|*secret*|*token*|*api_key*|*database_url*|*private_key*) printf '********' ;;
    *) printf '%s' "$value" ;;
  esac
}

backup_file_if_exists() {
  local path="$1"
  if [[ -f "$path" ]]; then
    local backup="${path}.bak.$(date +%Y%m%d%H%M%S)"
    cp -a "$path" "$backup"
    ok "Backup criado: $backup"
  fi
}

write_secure_file() {
  local path="$1"
  local content="$2"
  local owner="${3:-root:root}"
  install -d -m 0750 "$(dirname "$path")"
  umask 077
  printf '%s\n' "$content" > "$path"
  chmod 600 "$path"
  chown "$owner" "$path" 2>/dev/null || true
}
