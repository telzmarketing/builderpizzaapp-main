#!/usr/bin/env bash

is_true() {
  case "${1:-}" in
    true|TRUE|1|yes|YES|sim|SIM) return 0 ;;
    *) return 1 ;;
  esac
}

normalize_boolean() {
  local name="$1"
  local value="${!name:-}"
  case "${value,,}" in
    true|1|yes|sim) printf -v "$name" '%s' 'true' ;;
    false|0|no|nao) printf -v "$name" '%s' 'false' ;;
    *)
      fail "$name deve ser booleano (true ou false)"
      exit 1
      ;;
  esac
}

validate_database_mode() {
  case "$1" in
    local|external) return 0 ;;
    *)
      fail "DATABASE_MODE deve ser local ou external"
      exit 1
      ;;
  esac
}

validate_database_host() {
  local value="$1"
  [[ -n "$value" && ${#value} -le 253 && "$value" != *[[:space:]/@?#%]* ]] || {
    fail "DATABASE_HOST invalido"
    exit 1
  }
  if [[ "$value" == *:* ]]; then
    printf '%s' "$value" | /usr/bin/python3 -c \
      'import ipaddress, sys; ipaddress.IPv6Address(sys.stdin.read())' 2>/dev/null || {
        fail "DATABASE_HOST IPv6 invalido"
        exit 1
      }
    return 0
  fi
  local label
  IFS='.' read -r -a labels <<< "$value"
  for label in "${labels[@]}"; do
    [[ -n "$label" && ${#label} -le 63 && "$label" =~ ^[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?$ ]] || {
      fail "DATABASE_HOST invalido"
      exit 1
    }
  done
}

validate_monitoring_dir() {
  local value="$1"
  local canonical
  canonical="$(realpath -m -- "$value")" || {
    fail "PLATFORM_MONITORING_SNAPSHOT_DIR nao pode ser normalizado: $value"
    exit 1
  }
  if [[ "$value" != "$canonical" || ! "$canonical" =~ ^/var/lib/telz/[A-Za-z0-9._/-]+$ ]]; then
    fail "PLATFORM_MONITORING_SNAPSHOT_DIR deve ser um caminho canonico sob /var/lib/telz"
    exit 1
  fi
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
  local canonical parent
  canonical="$(realpath -m -- "$value")" || {
    fail "INSTALL_DIR nao pode ser normalizado: $value"
    exit 1
  }
  if [[ "$value" != "$canonical" || ! "$canonical" =~ ^/opt/[A-Za-z0-9][A-Za-z0-9._-]{0,63}$ ]]; then
    fail "INSTALL_DIR deve ser um caminho canonico direto sob /opt (ex.: /opt/telz)"
    exit 1
  fi
  parent="$(dirname -- "$canonical")"
  if [[ ! -d "$parent" || -L "$parent" || "$(stat -c '%U' "$parent")" != "root" || -n "$(find "$parent" -maxdepth 0 -perm /022 -print -quit)" ]]; then
    fail "Diretorio pai de INSTALL_DIR deve ser real, root-owned e nao gravavel por grupo/outros: $parent"
    exit 1
  fi
  if [[ -e "$canonical" || -L "$canonical" ]]; then
    if [[ ! -d "$canonical" || -L "$canonical" || "$(realpath -e -- "$canonical")" != "$canonical" ]]; then
      fail "INSTALL_DIR existente deve ser um diretorio real, sem symlink: $canonical"
      exit 1
    fi
  fi
}

validate_service_user() {
  local value="$1"
  if [[ ! "$value" =~ ^[a-z_][a-z0-9_-]{0,31}$ || "$value" == "root" ]]; then
    fail "SERVICE_USER invalido ou privilegiado"
    exit 1
  fi
  if id "$value" >/dev/null 2>&1 && [[ "$(id -u "$value")" -eq 0 ]]; then
    fail "SERVICE_USER nao pode possuir UID 0"
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
  local label
  [[ -n "$domain" && ${#domain} -le 253 ]] || return 1
  [[ "$domain" != http*://* && "$domain" != *"/"* && "$domain" != *":"* ]] || return 1
  [[ "$domain" == *.* && "$domain" =~ ^[A-Za-z0-9.-]+$ ]] || return 1
  [[ "$domain" != .* && "$domain" != *. && "$domain" != *..* ]] || return 1
  IFS='.' read -r -a labels <<< "$domain"
  for label in "${labels[@]}"; do
    [[ -n "$label" && ${#label} -le 63 ]] || return 1
    [[ "$label" =~ ^[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?$ ]] || return 1
  done
}

validate_port() {
  [[ "$1" =~ ^[0-9]+$ ]] && [[ "$1" -ge 1 ]] && [[ "$1" -le 65535 ]]
}

validate_worker_count() {
  [[ "$1" =~ ^[0-9]+$ ]] && [[ "$1" -ge 1 ]] && [[ "$1" -le 64 ]]
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
