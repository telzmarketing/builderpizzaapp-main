#!/usr/bin/env bash

TRUSTED_INSTALLER_ASSET_ROOT="${TRUSTED_INSTALLER_ASSET_ROOT:-/var/lib/telz-installer/trusted-assets}"
TRUSTED_INSTALLER_ASSET_POINTER="$TRUSTED_INSTALLER_ASSET_ROOT/current"
TRUSTED_INSTALLER_ASSET_PATHS=(
  installer/install.sh
  installer/config/defaults.env
  installer/lib/backup.sh
  installer/lib/backend.sh
  installer/lib/colors.sh
  installer/lib/database.sh
  installer/lib/firewall.sh
  installer/lib/frontend.sh
  installer/lib/git.sh
  installer/lib/nginx.sh
  installer/lib/prompts.sh
  installer/lib/ssl.sh
  installer/lib/summary.sh
  installer/lib/system.sh
  installer/lib/systemd.sh
  installer/lib/validation.sh
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
    if [[ "$asset" == scripts/* || "$asset" == "installer/install.sh" ]]; then
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
  printf 'commit=%s\ninstall_dir=%s\nsource_root=%s\n' "$commit" "$INSTALL_DIR" "$REPO_ROOT" > "$temporary"
  chown root:root "$temporary"
  chmod 0400 "$temporary"
  mv -f -- "$temporary" "$TRUSTED_INSTALLER_ASSET_POINTER"
}

install_trusted_resume_launcher() {
  local temporary
  temporary="$(mktemp /usr/local/sbin/.telz-installer-resume.XXXXXX)"
  cat > "$temporary" <<'RUNNER'
#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
root=/var/lib/telz-installer/trusted-assets
pointer="$root/current"
[[ "${EUID:-$(id -u)}" -eq 0 ]] || { echo "execute como root" >&2; exit 1; }
[[ -f "$pointer" && ! -L "$pointer" && "$(stat -c '%U:%G %a' "$pointer")" == "root:root 400" ]] || exit 1
mapfile -t values < "$pointer"
[[ "${#values[@]}" -eq 3 && "${values[0]}" =~ ^commit=(source\.[A-Za-z0-9]+)$ ]] || exit 1
stage="$root/${values[0]#commit=}"
install_dir="${values[1]#install_dir=}"
source_root="${values[2]#source_root=}"
[[ "${values[1]}" == install_dir=* && "$install_dir" =~ ^/opt/[A-Za-z0-9][A-Za-z0-9._-]{0,63}$ ]] || exit 1
[[ "${values[2]}" == source_root=/* && -d "$source_root" && ! -L "$source_root" ]] || exit 1
[[ -d "$stage" && ! -L "$stage" && "$(stat -c '%U:%G %a' "$stage")" == "root:root 700" ]] || exit 1
[[ -f "$stage/.manifest.sha256" && ! -L "$stage/.manifest.sha256" && "$(stat -c '%U:%G %a' "$stage/.manifest.sha256")" == "root:root 400" ]] || exit 1
test -z "$(find "$stage" -mindepth 1 -type l -print -quit)"
test -z "$(find "$stage" -mindepth 1 ! -type d ! -type f -print -quit)"
(cd "$stage" && sha256sum --check --strict .manifest.sha256 >/dev/null)
[[ -x "$stage/installer/install.sh" && ! -L "$stage/installer/install.sh" && "$(stat -c '%U:%G %a' "$stage/installer/install.sh")" == "root:root 500" ]] || exit 1
exec env TELZ_TRUSTED_INSTALLER_RUNNER=true TELZ_INSTALLER_SOURCE_ROOT="$source_root" \
  "$stage/installer/install.sh" "$@"
RUNNER
  chown root:root "$temporary"
  chmod 0500 "$temporary"
  mv -f -- "$temporary" /usr/local/sbin/telz-installer-resume
}

stage_trusted_installer_assets() {
  local stage
  install -d -m 0700 -o root -g root "$TRUSTED_INSTALLER_ASSET_ROOT"
  [[ ! -L "$TRUSTED_INSTALLER_ASSET_ROOT" && "$(stat -c '%U:%G %a' "$TRUSTED_INSTALLER_ASSET_ROOT")" == "root:root 700" ]] || {
    fail "Raiz de ativos confiaveis do instalador e insegura"
    return 1
  }
  stage="$(mktemp -d "$TRUSTED_INSTALLER_ASSET_ROOT/source.XXXXXX")"
  chown root:root "$stage"
  chmod 0700 "$stage"
  /usr/bin/python3 - "$REPO_ROOT" "$stage" "${TRUSTED_INSTALLER_ASSET_PATHS[@]}" <<'PY'
import hashlib, os, stat, sys

source_root, destination_root, *assets = sys.argv[1:]
source_root_fd = os.open(source_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
destination_root_fd = os.open(destination_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
manifest = []
try:
    for asset in assets:
        parts = asset.split("/")
        if not parts or any(part in ("", ".", "..") for part in parts):
            raise SystemExit(f"caminho de ativo invalido: {asset}")
        source_dir_fd = os.dup(source_root_fd)
        destination_dir_fd = os.dup(destination_root_fd)
        try:
            for component in parts[:-1]:
                next_source_fd = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=source_dir_fd)
                os.close(source_dir_fd)
                source_dir_fd = next_source_fd
                try:
                    os.mkdir(component, 0o700, dir_fd=destination_dir_fd)
                except FileExistsError:
                    pass
                next_destination_fd = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=destination_dir_fd)
                os.close(destination_dir_fd)
                destination_dir_fd = next_destination_fd
            source_fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW, dir_fd=source_dir_fd)
            if not stat.S_ISREG(os.fstat(source_fd).st_mode):
                raise SystemExit(f"ativo nao e arquivo regular: {asset}")
            file_mode = 0o500 if asset.startswith("scripts/") or asset == "installer/install.sh" else 0o400
            destination_fd = os.open(parts[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, file_mode, dir_fd=destination_dir_fd)
            digest = hashlib.sha256()
            try:
                while chunk := os.read(source_fd, 1024 * 1024):
                    digest.update(chunk)
                    os.write(destination_fd, chunk)
                os.fchmod(destination_fd, file_mode)
                os.fchown(destination_fd, 0, 0)
                os.fsync(destination_fd)
            finally:
                os.close(source_fd)
                os.close(destination_fd)
            manifest.append(f"{digest.hexdigest()}  {asset}\n")
        finally:
            os.close(source_dir_fd)
            os.close(destination_dir_fd)
    manifest_fd = os.open(".manifest.sha256", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400, dir_fd=destination_root_fd)
    try:
        os.write(manifest_fd, "".join(manifest).encode("utf-8"))
        os.fchmod(manifest_fd, 0o400)
        os.fchown(manifest_fd, 0, 0)
        os.fsync(manifest_fd)
    finally:
        os.close(manifest_fd)
    os.fsync(destination_root_fd)
finally:
    os.close(source_root_fd)
    os.close(destination_root_fd)
PY
  chown root:root "$stage/.manifest.sha256"
  chmod 0400 "$stage/.manifest.sha256"
  validate_trusted_installer_asset_dir "$stage" || {
    fail "Staging confiavel falhou na validacao final"
    return 1
  }
  write_trusted_installer_asset_pointer "$(basename -- "$stage")"
  install_trusted_resume_launcher
  TRUSTED_INSTALLER_ASSETS_DIR="$stage"
  export TRUSTED_INSTALLER_ASSETS_DIR
  ok "Ativos operacionais selados antes das fases executadas pelo usuario de servico"
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
  [[ "${#pointer_lines[@]}" -eq 3 && "${pointer_lines[0]}" =~ ^commit=(source\.[A-Za-z0-9]+)$ ]] || {
    fail "Ponteiro de ativos confiaveis invalido"
    return 1
  }
  commit="${pointer_lines[0]#commit=}"
  recorded_install_dir="${pointer_lines[1]#install_dir=}"
  [[ "${pointer_lines[1]}" == install_dir=* && "$recorded_install_dir" == "$INSTALL_DIR" ]] || {
    fail "Staging confiavel pertence a outro INSTALL_DIR"
    return 1
  }
  [[ "${pointer_lines[2]}" == "source_root=$REPO_ROOT" ]] || {
    fail "Staging confiavel pertence a outra origem"
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

cleanup_trusted_installer_assets() {
  local trusted_dir="${TRUSTED_INSTALLER_ASSETS_DIR:-}"
  [[ -n "$trusted_dir" && "$trusted_dir" == "$TRUSTED_INSTALLER_ASSET_ROOT"/source.* ]] || {
    fail "Recusa de limpeza: staging confiavel nao identificado"
    return 1
  }
  validate_trusted_installer_asset_dir "$trusted_dir" || {
    fail "Recusa de limpeza: staging confiavel nao passou na verificacao final"
    return 1
  }
  rm -rf -- "$trusted_dir"
  rm -f -- "$TRUSTED_INSTALLER_ASSET_POINTER" "$STATE_DIR/00_trusted_assets.done" \
    /usr/local/sbin/telz-installer-resume
  unset TRUSTED_INSTALLER_ASSETS_DIR
  ok "Staging privilegiado removido apos conclusao bem-sucedida"
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
