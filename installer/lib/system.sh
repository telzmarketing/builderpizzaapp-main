#!/usr/bin/env bash

TRUSTED_INSTALLER_ASSET_ROOT="${TRUSTED_INSTALLER_ASSET_ROOT:-/var/lib/telz-installer/trusted-assets}"
TRUSTED_INSTALLER_ASSET_POINTER="$TRUSTED_INSTALLER_ASSET_ROOT/current"
TRUSTED_INSTALLER_ASSET_PATHS=(
  scripts/backup-telz.sh
  scripts/collect-telz-monitoring.sh
  scripts/finish-ssl.sh
  scripts/health-check.sh
  installer/templates/nginx-telz.conf
  installer/templates/telz-api.service
  installer/templates/telz-monitoring.service
  installer/templates/telz-monitoring.timer
  installer/templates/telz-web.service
  installer/templates/telz-whatsapp-gateway.service
)

is_trusted_installer_asset_name() {
  local requested="$1"
  local allowed
  for allowed in "${TRUSTED_INSTALLER_ASSET_PATHS[@]}"; do
    [[ "$requested" == "$allowed" ]] && return 0
  done
  return 1
}

validate_trusted_installer_asset_dir() {
  local stage="$1"
  local asset candidate recorded_hash actual_hash mode
  local -A manifest_hashes=()
  [[ -d "$stage" && ! -L "$stage" && "$(stat -c '%U:%G %a' "$stage")" == "root:root 700" ]] || return 1
  [[ -z "$(find "$stage" -mindepth 1 -type l -print -quit)" ]] || return 1
  [[ -z "$(find "$stage" -mindepth 1 ! -type d ! -type f -print -quit)" ]] || return 1
  [[ -f "$stage/.manifest.sha256" && ! -L "$stage/.manifest.sha256" ]] || return 1
  [[ "$(stat -c '%U:%G %a' "$stage/.manifest.sha256")" == "root:root 400" ]] || return 1
  while read -r recorded_hash asset; do
    [[ "$recorded_hash" =~ ^[0-9a-f]{64}$ ]] || return 1
    is_trusted_installer_asset_name "$asset" || return 1
    [[ -z "${manifest_hashes[$asset]:-}" ]] || return 1
    manifest_hashes["$asset"]="$recorded_hash"
  done < "$stage/.manifest.sha256"
  [[ "${#manifest_hashes[@]}" -eq "${#TRUSTED_INSTALLER_ASSET_PATHS[@]}" ]] || return 1
  for asset in "${TRUSTED_INSTALLER_ASSET_PATHS[@]}"; do
    candidate="$stage/$asset"
    [[ -f "$candidate" && ! -L "$candidate" && "$(stat -c '%U:%G' "$candidate")" == "root:root" ]] || return 1
    mode="$(stat -c '%a' "$candidate")"
    if [[ "$asset" == scripts/* ]]; then
      [[ "$mode" == "500" ]] || return 1
    else
      [[ "$mode" == "400" ]] || return 1
    fi
    actual_hash="$(sha256sum -- "$candidate")"
    actual_hash="${actual_hash%% *}"
    [[ "$actual_hash" == "${manifest_hashes[$asset]}" ]] || return 1
  done
}

write_trusted_installer_asset_pointer() {
  local commit="$1"
  local temporary
  temporary="$(mktemp "$TRUSTED_INSTALLER_ASSET_ROOT/.current.XXXXXX")"
  printf 'commit=%s\ninstall_dir=%s\n' "$commit" "$INSTALL_DIR" > "$temporary"
  chown root:root "$temporary"
  chmod 0400 "$temporary"
  mv -f -- "$temporary" "$TRUSTED_INSTALLER_ASSET_POINTER"
}

stage_trusted_installer_assets() {
  local commit stage target asset destination metadata mode type object listed_path
  local -a tree_entry
  install -d -m 0700 -o root -g root "$TRUSTED_INSTALLER_ASSET_ROOT"
  [[ ! -L "$TRUSTED_INSTALLER_ASSET_ROOT" && "$(stat -c '%U:%G %a' "$TRUSTED_INSTALLER_ASSET_ROOT")" == "root:root 700" ]] || {
    fail "Raiz de ativos confiaveis do instalador e insegura"
    return 1
  }
  commit="$(sudo -u "$SERVICE_USER" -H git -C "$INSTALL_DIR" rev-parse --verify 'HEAD^{commit}')"
  [[ "$commit" =~ ^[0-9a-f]{40}$ ]] || {
    fail "Commit do checkout invalido para staging confiavel"
    return 1
  }
  target="$TRUSTED_INSTALLER_ASSET_ROOT/$commit"
  if [[ -e "$target" || -L "$target" ]]; then
    validate_trusted_installer_asset_dir "$target" || {
      fail "Staging confiavel existente possui integridade invalida: $target"
      return 1
    }
    write_trusted_installer_asset_pointer "$commit"
    TRUSTED_INSTALLER_ASSETS_DIR="$target"
    export TRUSTED_INSTALLER_ASSETS_DIR
    return 0
  fi
  stage="$(mktemp -d "$TRUSTED_INSTALLER_ASSET_ROOT/.stage.${commit}.XXXXXX")"
  chown root:root "$stage"
  chmod 0700 "$stage"
  : > "$stage/.manifest.sha256"
  for asset in "${TRUSTED_INSTALLER_ASSET_PATHS[@]}"; do
    mapfile -t tree_entry < <(sudo -u "$SERVICE_USER" -H git -C "$INSTALL_DIR" ls-tree "$commit" -- "$asset")
    [[ "${#tree_entry[@]}" -eq 1 ]] || {
      fail "Ativo obrigatorio ausente do commit $commit: $asset"
      return 1
    }
    metadata="${tree_entry[0]}"
    IFS=$' \t' read -r mode type object listed_path <<< "$metadata"
    [[ "$type" == "blob" && "$mode" =~ ^100(644|755)$ && "$object" =~ ^[0-9a-f]{40,64}$ && "$listed_path" == "$asset" ]] || {
      fail "Tipo Git invalido para ativo confiavel: $asset"
      return 1
    }
    destination="$stage/$asset"
    install -d -m 0700 -o root -g root "$(dirname -- "$destination")"
    sudo -u "$SERVICE_USER" -H git -C "$INSTALL_DIR" cat-file blob "$object" > "$destination"
    [[ "$(git hash-object --no-filters "$destination")" == "$object" ]] || {
      fail "Conteudo do ativo divergiu do objeto Git: $asset"
      return 1
    }
    chown root:root "$destination"
    if [[ "$asset" == scripts/* ]]; then
      chmod 0500 "$destination"
    else
      chmod 0400 "$destination"
    fi
    printf '%s  %s\n' "$(sha256sum -- "$destination" | awk '{print $1}')" "$asset" >> "$stage/.manifest.sha256"
  done
  chown root:root "$stage/.manifest.sha256"
  chmod 0400 "$stage/.manifest.sha256"
  validate_trusted_installer_asset_dir "$stage" || {
    fail "Staging confiavel falhou na validacao final"
    return 1
  }
  mv -- "$stage" "$target"
  write_trusted_installer_asset_pointer "$commit"
  TRUSTED_INSTALLER_ASSETS_DIR="$target"
  export TRUSTED_INSTALLER_ASSETS_DIR
  ok "Ativos operacionais selados a partir do commit $commit"
}

load_trusted_installer_assets() {
  local -a pointer_lines
  local commit recorded_install_dir target
  [[ -f "$TRUSTED_INSTALLER_ASSET_POINTER" && ! -L "$TRUSTED_INSTALLER_ASSET_POINTER" ]] || {
    fail "Ponteiro de ativos confiaveis ausente; nao e seguro retomar fases root"
    return 1
  }
  [[ "$(stat -c '%U:%G %a' "$TRUSTED_INSTALLER_ASSET_POINTER")" == "root:root 400" ]] || {
    fail "Ponteiro de ativos confiaveis possui metadados invalidos"
    return 1
  }
  mapfile -t pointer_lines < "$TRUSTED_INSTALLER_ASSET_POINTER"
  [[ "${#pointer_lines[@]}" -eq 2 && "${pointer_lines[0]}" =~ ^commit=([0-9a-f]{40})$ ]] || {
    fail "Ponteiro de ativos confiaveis invalido"
    return 1
  }
  commit="${pointer_lines[0]#commit=}"
  recorded_install_dir="${pointer_lines[1]#install_dir=}"
  [[ "${pointer_lines[1]}" == install_dir=* && "$recorded_install_dir" == "$INSTALL_DIR" ]] || {
    fail "Staging confiavel pertence a outro INSTALL_DIR"
    return 1
  }
  target="$TRUSTED_INSTALLER_ASSET_ROOT/$commit"
  validate_trusted_installer_asset_dir "$target" || {
    fail "Ativos confiaveis nao passaram na verificacao de integridade"
    return 1
  }
  TRUSTED_INSTALLER_ASSETS_DIR="$target"
  export TRUSTED_INSTALLER_ASSETS_DIR
}

trusted_installer_asset() {
  local asset="$1"
  local candidate
  is_trusted_installer_asset_name "$asset" || {
    fail "Ativo nao pertence a allowlist do instalador: $asset"
    return 1
  }
  [[ -n "${TRUSTED_INSTALLER_ASSETS_DIR:-}" ]] || load_trusted_installer_assets
  candidate="$TRUSTED_INSTALLER_ASSETS_DIR/$asset"
  [[ -f "$candidate" && ! -L "$candidate" && "$(stat -c '%U:%G' "$candidate")" == "root:root" ]] || {
    fail "Ativo confiavel indisponivel: $asset"
    return 1
  }
  printf '%s\n' "$candidate"
}

detect_os() {
  if [[ ! -r /etc/os-release ]]; then
    fail "Nao foi possivel detectar o sistema operacional."
    exit 1
  fi
  . /etc/os-release
  if [[ "${ID:-}" != "ubuntu" ]]; then
    fail "Sistema nao suportado nesta versao: ${PRETTY_NAME:-desconhecido}. Use Ubuntu 22.04/24.04."
    exit 1
  fi
  case "${VERSION_ID:-}" in
    22.04|24.04) ok "Ubuntu suportado: ${VERSION_ID}" ;;
    *) warn "Ubuntu ${VERSION_ID:-desconhecido}; suporte principal esperado: 22.04/24.04." ;;
  esac
}

install_system_packages() {
  info "Instalando pacotes base"
  apt-get update
  local -a python_packages=(python3 python3-venv python3-dev python3-pip)
  if [[ "${VERSION_ID:-}" == "24.04" ]]; then
    python_packages=(python3.12 python3.12-venv python3.12-dev python3-pip)
  fi
  DEBIAN_FRONTEND=noninteractive apt-get install -y \
    ca-certificates curl wget git unzip build-essential software-properties-common \
    gnupg ufw nginx "${python_packages[@]}" postgresql postgresql-contrib
  command -v python3.12 >/dev/null 2>&1 || {
    fail "Python 3.12 e obrigatorio. No Ubuntu 22.04, provisione python3.12 + venv previamente por uma fonte aprovada."
    return 1
  }
  [[ "$(python3.12 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')" == "3.12" ]] || {
    fail "O interpretador python3.12 nao corresponde a Python 3.12."
    return 1
  }
}

ensure_service_user() {
  if id "$SERVICE_USER" >/dev/null 2>&1; then
    ok "Usuario existente: $SERVICE_USER"
  else
    adduser --disabled-password --gecos "" "$SERVICE_USER"
    ok "Usuario criado: $SERVICE_USER"
  fi
}

prepare_directories() {
  validate_install_dir "$INSTALL_DIR"
  mkdir -p "$INSTALL_DIR" /var/log/telz-installer /var/lib/telz-installer/state
  install -d -m 0700 -o root -g root /var/backups/telz
  chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
  chmod 750 "$INSTALL_DIR"
}
