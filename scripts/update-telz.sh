#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

ERROR_HANDLER_ARMED=false

die() {
  echo "[update][erro] $*" >&2
  if [[ "${ERROR_HANDLER_ARMED:-false}" == "true" ]]; then
    on_error 1
  fi
  exit 1
}

require_root_owned_file() {
  local candidate="$1"
  [[ -f "$candidate" && ! -L "$candidate" ]] || die "arquivo root-owned invalido: $candidate"
  [[ "$(stat -c '%U' "$candidate")" == "root" ]] || die "arquivo deve pertencer a root: $candidate"
  [[ "$(stat -c '%h' "$candidate")" == "1" ]] || die "arquivo nao pode possuir hardlinks adicionais: $candidate"
  [[ -z "$(find "$candidate" -maxdepth 0 -perm /022 -print -quit)" ]] || \
    die "arquivo nao pode ser gravavel por grupo/outros: $candidate"
}

require_root_owned_executable() {
  local candidate="$1"
  require_root_owned_file "$candidate"
  [[ -x "$candidate" ]] || die "arquivo deve ser executavel: $candidate"
}

SOURCE_SCRIPT="$(realpath -e "$0")"
require_root_owned_executable "$SOURCE_SCRIPT"

if [[ "${TELZ_UPDATE_REEXEC:-false}" != "true" ]]; then
  TEMP_SCRIPT="$(mktemp /tmp/telz-update.XXXXXX)"
  install -m 0700 -o root -g root "$SOURCE_SCRIPT" "$TEMP_SCRIPT"
  exec env TELZ_UPDATE_REEXEC=true TELZ_UPDATE_TEMP_SCRIPT="$TEMP_SCRIPT" bash "$TEMP_SCRIPT" "$@"
fi

cleanup_temporary_state() {
  if [[ -n "${TELZ_UPDATE_TEMP_SCRIPT:-}" && "$TELZ_UPDATE_TEMP_SCRIPT" == /tmp/telz-update.* ]]; then
    rm -f -- "$TELZ_UPDATE_TEMP_SCRIPT"
  fi
  if [[ -n "${OPERATIONS_STATE_DIR:-}" && "$OPERATIONS_STATE_DIR" == /tmp/telz-operations-state.* && -d "$OPERATIONS_STATE_DIR" ]]; then
    rm -rf -- "$OPERATIONS_STATE_DIR"
  fi
  if [[ -n "${UNIT_STAGE_DIR:-}" && "$UNIT_STAGE_DIR" == /tmp/telz-unit-stage.* && -d "$UNIT_STAGE_DIR" ]]; then
    rm -rf -- "$UNIT_STAGE_DIR"
  fi
  if [[ "${BUILD_IN_PROGRESS:-false}" == "true" ]]; then
    if ! discard_partial_release; then
      echo "[update][erro] release parcial preservada para inspecao: ${FINAL_RELEASE_DIR:-desconhecida}" >&2
    fi
  fi
}
trap cleanup_temporary_state EXIT

[[ "${EUID:-$(id -u)}" -eq 0 ]] || die "execute como root"

INSTALL_DIR="$(realpath -e "${1:-/opt/telz}")"
SERVICE_USER="${TELZ_SERVICE_USER:-telz}"
BRANCH="${BRANCH:-main}"
RUN_TESTS="${RUN_TESTS:-false}"
EXPECTED_COMMIT="${TELZ_EXPECTED_COMMIT:-}"
ALEMBIC_TARGET="${TELZ_ALEMBIC_TARGET:-20260818_platform_operations}"
REQUIRE_PUBLIC_HTTPS="${TELZ_REQUIRE_PUBLIC_HTTPS:-true}"
PUBLIC_HEALTH_URL="${TELZ_PUBLIC_HEALTH_URL:-}"
OPERATION_BUNDLE_INPUT="${TELZ_OPERATION_BUNDLE_DIR:-}"
SOURCE_ARCHIVE_INPUT="${TELZ_SOURCE_ARCHIVE:-}"
SOURCE_ARCHIVE_SHA256="${TELZ_SOURCE_ARCHIVE_SHA256:-}"
PREVIOUS_SOURCE_ARCHIVE_INPUT="${TELZ_PREVIOUS_SOURCE_ARCHIVE:-}"
PREVIOUS_SOURCE_ARCHIVE_SHA256="${TELZ_PREVIOUS_SOURCE_ARCHIVE_SHA256:-}"
EXPECTED_PREVIOUS_COMMIT="${TELZ_PREVIOUS_COMMIT:-}"
DEPENDENCY_ARCHIVE_INPUT="${TELZ_DEPENDENCY_ARCHIVE:-}"
DEPENDENCY_ARCHIVE_SHA256="${TELZ_DEPENDENCY_ARCHIVE_SHA256:-}"
BUILD_USER="${TELZ_BUILD_USER:-telz-build}"
BUILD_GROUP="${TELZ_BUILD_GROUP:-telz-build}"
BUILD_HOME=""
RELEASES_DIR="/var/lib/telz/releases"
CURRENT_LINK="/var/lib/telz/current"
UPDATE_COMMAND="/usr/local/sbin/update-telz"
BACKUP_COMMAND="/usr/local/bin/backup-telz"
HEALTH_COMMAND="/usr/local/sbin/telz-health-check"
COLLECTOR_COMMAND="/usr/local/sbin/telz-monitoring-collector"
RESTORE_COMMAND="/usr/local/sbin/restore-telz"
ROLLBACK_COMMAND="/usr/local/sbin/rollback-telz"
SSL_COMMAND="/usr/local/sbin/telz-finish-ssl"

[[ "$INSTALL_DIR" = /* && "$INSTALL_DIR" != "/" && -d "$INSTALL_DIR/.git" ]] || die "INSTALL_DIR invalido"
[[ -d "$INSTALL_DIR/backend" && ! -L "$INSTALL_DIR/backend" ]] || die "backend persistente invalido"
[[ -f "$INSTALL_DIR/backend/.env" && ! -L "$INSTALL_DIR/backend/.env" ]] || die "backend/.env persistente ausente"
[[ ! -L "$INSTALL_DIR/.runtime" ]] || die ".runtime persistente nao pode ser symlink"
[[ ! -L "$INSTALL_DIR/uploads" ]] || die "uploads persistente nao pode ser symlink"
[[ "$BRANCH" =~ ^[A-Za-z0-9][A-Za-z0-9._/-]*$ ]] || die "branch invalida"
[[ "$EXPECTED_COMMIT" =~ ^[0-9a-f]{40}$ ]] || die "TELZ_EXPECTED_COMMIT deve ser um SHA-1 completo"
[[ "$ALEMBIC_TARGET" =~ ^[A-Za-z0-9_]+$ ]] || die "TELZ_ALEMBIC_TARGET invalido"
[[ "$RUN_TESTS" == "true" || "$RUN_TESTS" == "false" ]] || die "RUN_TESTS deve ser true ou false"
[[ "$SOURCE_ARCHIVE_SHA256" =~ ^[0-9a-f]{64}$ ]] || die "TELZ_SOURCE_ARCHIVE_SHA256 invalido"
[[ "$PREVIOUS_SOURCE_ARCHIVE_SHA256" =~ ^[0-9a-f]{64}$ ]] || die "TELZ_PREVIOUS_SOURCE_ARCHIVE_SHA256 invalido"
[[ "$EXPECTED_PREVIOUS_COMMIT" =~ ^[0-9a-f]{40}$ ]] || die "TELZ_PREVIOUS_COMMIT invalido"
[[ "$DEPENDENCY_ARCHIVE_SHA256" =~ ^[0-9a-f]{64}$ ]] || die "TELZ_DEPENDENCY_ARCHIVE_SHA256 invalido"
[[ "$REQUIRE_PUBLIC_HTTPS" == "true" || "$REQUIRE_PUBLIC_HTTPS" == "false" ]] || \
  die "TELZ_REQUIRE_PUBLIC_HTTPS deve ser true ou false"
if [[ "$REQUIRE_PUBLIC_HTTPS" == "true" ]]; then
  [[ "$PUBLIC_HEALTH_URL" == "https://erp.telz.com.br/health" ]] || \
    die "TELZ_PUBLIC_HEALTH_URL deve ser a URL canonica HTTPS aprovada"
fi
[[ "$OPERATION_BUNDLE_INPUT" = /* && ! -L "$OPERATION_BUNDLE_INPUT" ]] || \
  die "TELZ_OPERATION_BUNDLE_DIR deve ser absoluto e nao pode ser symlink"
OPERATION_BUNDLE_DIR="$(realpath -e "$OPERATION_BUNDLE_INPUT")"
[[ -d "$OPERATION_BUNDLE_DIR" && ! -L "$OPERATION_BUNDLE_DIR" ]] || die "bundle operacional invalido"
id "$SERVICE_USER" >/dev/null 2>&1 || die "usuario de servico inexistente: $SERVICE_USER"
for persistent_dir in "$INSTALL_DIR/uploads" "$INSTALL_DIR/.runtime"; do
  [[ -d "$persistent_dir" && ! -L "$persistent_dir" ]] || die "diretorio persistente ausente ou inseguro: $persistent_dir"
  [[ "$(stat -c '%U:%G' "$persistent_dir")" == "$SERVICE_USER:$SERVICE_USER" ]] || die "ownership persistente invalido: $persistent_dir"
  [[ -z "$(find "$persistent_dir" -maxdepth 0 -perm /022 -print -quit)" ]] || die "diretorio persistente gravavel por grupo/outros: $persistent_dir"
done
sudo -u "$SERVICE_USER" -H git check-ref-format --branch "$BRANCH" >/dev/null 2>&1 || die "branch invalida"

BUNDLE_FILES=(
  scripts/update-telz.sh
  scripts/backup-telz.sh
  scripts/health-check.sh
  scripts/collect-telz-monitoring.sh
  scripts/restore-telz.sh
  scripts/rollback-telz.sh
  scripts/finish-ssl.sh
  scripts/build-telz-release.sh
  installer/templates/telz-api.service
  installer/templates/telz-web.service
  installer/templates/telz-whatsapp-gateway.service
  installer/templates/telz-monitoring.service
  installer/templates/telz-monitoring.timer
)
for relative_path in "${BUNDLE_FILES[@]}"; do
  require_root_owned_file "$OPERATION_BUNDLE_DIR/$relative_path"
done
for relative_path in "${BUNDLE_FILES[@]:0:8}"; do
  require_root_owned_executable "$OPERATION_BUNDLE_DIR/$relative_path"
  bash -n "$OPERATION_BUNDLE_DIR/$relative_path"
done
[[ -z "$(find "$OPERATION_BUNDLE_DIR" -xdev -type l -print -quit)" ]] || die "bundle nao pode conter symlink"
[[ -z "$(find "$OPERATION_BUNDLE_DIR" -xdev ! -type d ! -type f -print -quit)" ]] || die "bundle contem tipo especial"
[[ -z "$(find "$OPERATION_BUNDLE_DIR" -xdev ! -user root -print -quit)" ]] || die "bundle deve pertencer integralmente a root"
[[ -z "$(find "$OPERATION_BUNDLE_DIR" -xdev -perm /022 -print -quit)" ]] || die "bundle nao pode ser gravavel por grupo/outros"
mapfile -t ACTUAL_BUNDLE_FILES < <(cd "$OPERATION_BUNDLE_DIR" && find . -type f -printf '%P\n' | LC_ALL=C sort)
mapfile -t EXPECTED_BUNDLE_FILES < <(printf '%s\n' "${BUNDLE_FILES[@]}" | LC_ALL=C sort)
[[ "$(printf '%s\n' "${ACTUAL_BUNDLE_FILES[@]}")" == "$(printf '%s\n' "${EXPECTED_BUNDLE_FILES[@]}")" ]] || \
  die "bundle operacional contem lista inesperada"

BUNDLE_UPDATE="$OPERATION_BUNDLE_DIR/scripts/update-telz.sh"
BUNDLE_BACKUP="$OPERATION_BUNDLE_DIR/scripts/backup-telz.sh"
BUNDLE_HEALTH="$OPERATION_BUNDLE_DIR/scripts/health-check.sh"
BUNDLE_COLLECTOR="$OPERATION_BUNDLE_DIR/scripts/collect-telz-monitoring.sh"
BUNDLE_RESTORE="$OPERATION_BUNDLE_DIR/scripts/restore-telz.sh"
BUNDLE_ROLLBACK="$OPERATION_BUNDLE_DIR/scripts/rollback-telz.sh"
BUNDLE_SSL="$OPERATION_BUNDLE_DIR/scripts/finish-ssl.sh"
BUNDLE_BUILD="$OPERATION_BUNDLE_DIR/scripts/build-telz-release.sh"
BUNDLE_API_UNIT="$OPERATION_BUNDLE_DIR/installer/templates/telz-api.service"
BUNDLE_WEB_UNIT="$OPERATION_BUNDLE_DIR/installer/templates/telz-web.service"
BUNDLE_GATEWAY_UNIT="$OPERATION_BUNDLE_DIR/installer/templates/telz-whatsapp-gateway.service"
BUNDLE_MONITOR_UNIT="$OPERATION_BUNDLE_DIR/installer/templates/telz-monitoring.service"
BUNDLE_MONITOR_TIMER="$OPERATION_BUNDLE_DIR/installer/templates/telz-monitoring.timer"

LOCK_DIR="/run/lock/telz"
LOCK_FILE="$LOCK_DIR/maintenance.lock"
[[ ! -L "$LOCK_DIR" ]] || die "diretorio de lock nao pode ser symlink"
if [[ ! -e "$LOCK_DIR" ]]; then
  mkdir -m 0700 "$LOCK_DIR"
  chown root:root "$LOCK_DIR"
fi
[[ -d "$LOCK_DIR" && ! -L "$LOCK_DIR" && "$(stat -c '%U:%G %a' "$LOCK_DIR")" == "root:root 700" ]] || \
  die "diretorio de lock inseguro"
if [[ -e "$LOCK_FILE" || -L "$LOCK_FILE" ]]; then
  [[ -f "$LOCK_FILE" && ! -L "$LOCK_FILE" && "$(stat -c '%U:%G:%h' "$LOCK_FILE")" == "root:root:1" ]] || \
    die "arquivo de lock inseguro"
  [[ -z "$(find "$LOCK_FILE" -maxdepth 0 -perm /022 -print -quit)" ]] || die "arquivo de lock gravavel por grupo/outros"
else
  (set -o noclobber; : > "$LOCK_FILE")
  chown root:root "$LOCK_FILE"
  chmod 0600 "$LOCK_FILE"
fi
exec 9<>"$LOCK_FILE"
[[ "$(stat -Lc '%d:%i' /proc/$$/fd/9)" == "$(stat -Lc '%d:%i' "$LOCK_FILE")" ]] || die "inode do lock divergiu"
flock -n 9 || die "outra manutencao Telz esta em execucao"

as_service() {
  sudo -u "$SERVICE_USER" -H -- "$@"
}

prepare_public_build_config() {
  local destination="$1"
  local source="$DEPENDENCY_DIR/.telz-public-build.json"
  require_root_owned_file "$source"
  /usr/bin/python3 - "$source" <<'PY'
import json
import sys
from pathlib import Path

expected = {
    "VITE_API_URL": "",
    "VITE_MULTI_TENANT_AUTH_ENABLED": "true",
    "VITE_PLATFORM_HOSTNAME": "erp.telz.com.br",
    "VITE_PLATFORM_HOSTNAMES": "erp.telz.com.br",
}
if json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")) != expected:
    raise SystemExit("configuracao publica promovida diverge do contrato")
PY
  install -m 0400 -o "$BUILD_USER" -g "$BUILD_GROUP" "$source" "$destination"
}

require_source_archive() {
  local archive_input="$1"
  local expected_sha256="$2"
  local expected_commit="$3"
  local archive
  [[ "$archive_input" = /* && ! -L "$archive_input" ]] || die "archive fonte deve ser absoluto e real"
  archive="$(realpath -e "$archive_input")"
  require_root_owned_file "$archive"
  [[ "$(sha256sum "$archive" | awk '{print $1}')" == "$expected_sha256" ]] || die "SHA-256 do archive fonte divergiu"
  /usr/bin/python3 - "$archive" "$expected_commit" <<'PY'
import sys
import tarfile
from pathlib import PurePosixPath

archive_path, expected_commit = sys.argv[1], sys.argv[2]
seen = set()
marker = None
with tarfile.open(archive_path, "r:gz") as archive:
    for member in archive.getmembers():
        path = PurePosixPath(member.name)
        if not member.name or path.is_absolute() or ".." in path.parts or "." in path.parts:
            raise SystemExit("archive fonte contem caminho inseguro")
        if member.name in seen:
            raise SystemExit("archive fonte contem entrada duplicada")
        seen.add(member.name)
        if not (member.isdir() or member.isreg()):
            raise SystemExit("archive fonte contem tipo nao permitido")
        if member.name in {".git", ".telz-release.json", ".building", "backend/.env"}:
            raise SystemExit("archive fonte contem estado reservado")
        if member.name == ".telz-source-commit":
            if not member.isreg() or member.size > 64:
                raise SystemExit("marcador do archive fonte invalido")
            extracted = archive.extractfile(member)
            marker = extracted.read().decode("ascii").strip() if extracted else None
if marker != expected_commit:
    raise SystemExit("archive fonte diverge do commit esperado")
PY
  printf '%s\n' "$archive"
}

extract_source_archive() {
  local archive="$1"
  local destination="$2"
  /usr/bin/python3 - "$archive" "$destination" <<'PY'
import shutil
import sys
import tarfile
from pathlib import Path, PurePosixPath

destination = Path(sys.argv[2])
with tarfile.open(sys.argv[1], "r:gz") as archive:
    members = archive.getmembers()
    for member in sorted((item for item in members if item.isdir()), key=lambda item: len(PurePosixPath(item.name).parts)):
        target = destination.joinpath(*PurePosixPath(member.name).parts)
        target.mkdir(mode=0o700, parents=True, exist_ok=True)
    for member in (item for item in members if item.isreg()):
        target = destination.joinpath(*PurePosixPath(member.name).parts)
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        source = archive.extractfile(member)
        if source is None:
            raise SystemExit("entrada regular ilegivel")
        with target.open("xb") as output:
            shutil.copyfileobj(source, output)
        target.chmod(0o700 if member.mode & 0o111 else 0o600)
PY
}

require_dependency_archive() {
  local archive_input="$1"
  local expected_sha256="$2"
  local archive
  [[ "$archive_input" = /* && ! -L "$archive_input" ]] || die "archive de dependencias deve ser absoluto e real"
  archive="$(realpath -e "$archive_input")"
  require_root_owned_file "$archive"
  [[ "$(sha256sum "$archive" | awk '{print $1}')" == "$expected_sha256" ]] || die "SHA-256 das dependencias divergiu"
  /usr/bin/python3 - "$archive" "$EXPECTED_COMMIT" "$EXPECTED_PREVIOUS_COMMIT" <<'PY'
import json
import sys
import tarfile
from pathlib import PurePosixPath

seen = set()
metadata = None
public_config = None
with tarfile.open(sys.argv[1], "r:gz") as archive:
    for member in archive.getmembers():
        path = PurePosixPath(member.name)
        if not member.name or path.is_absolute() or ".." in path.parts or "." in path.parts:
            raise SystemExit("archive de dependencias contem caminho inseguro")
        if member.name in seen or not (member.isdir() or member.isreg()):
            raise SystemExit("archive de dependencias contem entrada invalida")
        if member.name not in {".telz-dependencies.json", ".telz-public-build.json"} and path.parts[0] not in {"wheelhouse", "pnpm-store"}:
            raise SystemExit("archive de dependencias contem caminho inesperado")
        seen.add(member.name)
        if member.name == ".telz-dependencies.json":
            source = archive.extractfile(member)
            metadata = json.load(source) if source else None
        elif member.name == ".telz-public-build.json":
            source = archive.extractfile(member)
            public_config = source.read() if source else None
if not isinstance(metadata, dict) or metadata.get("schema_version") != 1:
    raise SystemExit("metadata de dependencias invalida")
if metadata.get("target_commit") != sys.argv[2] or metadata.get("previous_commit") != sys.argv[3]:
    raise SystemExit("dependencias nao pertencem aos commits aprovados")
if metadata.get("python") != "3.12" or metadata.get("pip") != "25.1.1":
    raise SystemExit("toolchain Python das dependencias divergiu")
if metadata.get("node") != "22" or metadata.get("pnpm") != "10.14.0":
    raise SystemExit("toolchain Node das dependencias divergiu")
expected_public = {
    "VITE_API_URL": "",
    "VITE_MULTI_TENANT_AUTH_ENABLED": "true",
    "VITE_PLATFORM_HOSTNAME": "erp.telz.com.br",
    "VITE_PLATFORM_HOSTNAMES": "erp.telz.com.br",
}
if public_config is None or json.loads(public_config) != expected_public:
    raise SystemExit("configuracao publica promovida invalida")
import hashlib
if metadata.get("public_build_config_sha256") != hashlib.sha256(public_config).hexdigest():
    raise SystemExit("digest da configuracao publica promovida divergiu")
PY
  printf '%s\n' "$archive"
}

materialize_dependencies() {
  local dependency_root="/var/lib/telz/dependency-bundles"
  local final_dir="$dependency_root/$DEPENDENCY_ARCHIVE_SHA256"
  local temporary_dir="$dependency_root/.building-$DEPENDENCY_ARCHIVE_SHA256-$$"
  install -d -m 0755 -o root -g root "$dependency_root"
  [[ -d "$dependency_root" && ! -L "$dependency_root" && "$(stat -c '%U:%G' "$dependency_root")" == "root:root" ]] || \
    die "raiz de dependencias insegura"
  [[ -z "$(find "$dependency_root" -maxdepth 0 -perm /022 -print -quit)" ]] || die "raiz de dependencias gravavel"
  if [[ ! -d "$final_dir" ]]; then
    [[ ! -e "$temporary_dir" && ! -L "$temporary_dir" ]] || die "staging de dependencias ja existe"
    install -d -m 0700 -o root -g root "$temporary_dir"
    extract_source_archive "$DEPENDENCY_ARCHIVE" "$temporary_dir"
    [[ -d "$temporary_dir/wheelhouse" && -d "$temporary_dir/pnpm-store" ]] || die "dependencias promovidas incompletas"
    [[ -f "$temporary_dir/.telz-public-build.json" && ! -L "$temporary_dir/.telz-public-build.json" ]] || die "configuracao publica promovida ausente"
    chown -hR root:root "$temporary_dir"
    find "$temporary_dir" -xdev -type d -exec chmod 0555 {} +
    find "$temporary_dir" -xdev -type f -exec chmod 0444 {} +
    mv -- "$temporary_dir" "$final_dir"
  fi
  [[ -d "$final_dir" && ! -L "$final_dir" && "$(stat -c '%U:%G' "$final_dir")" == "root:root" ]] || die "dependencias materializadas invalidas"
  [[ -z "$(find "$final_dir" -xdev ! -user root -print -quit)" ]] || die "dependencias nao root-owned"
  [[ -z "$(find "$final_dir" -xdev -perm /022 -print -quit)" ]] || die "dependencias promovidas gravaveis"
  DEPENDENCY_DIR="$final_dir"
}

ensure_build_identity() {
  if ! getent group "$BUILD_GROUP" >/dev/null; then
    groupadd --system "$BUILD_GROUP"
  fi
  if ! id "$BUILD_USER" >/dev/null 2>&1; then
    useradd --system --gid "$BUILD_GROUP" --home-dir /nonexistent --shell /usr/sbin/nologin --no-create-home "$BUILD_USER"
  fi
  [[ "$BUILD_USER" != "$SERVICE_USER" ]] || die "usuario de build deve ser distinto do runtime"
  [[ "$(id -u "$BUILD_USER")" != "0" && "$(id -u "$BUILD_USER")" != "$(id -u "$SERVICE_USER")" ]] || die "UID do builder invalido"
  [[ "$(id -gn "$BUILD_USER")" == "$BUILD_GROUP" ]] || die "grupo primario do builder divergiu"
  [[ "$(id -nG "$BUILD_USER" | wc -w)" -eq 1 ]] || die "builder nao pode possuir grupos suplementares"
  [[ "$(getent passwd "$BUILD_USER" | cut -d: -f6-7)" == "/nonexistent:/usr/sbin/nologin" ]] || die "conta do builder possui home ou shell inesperado"
}

run_isolated_release_build() {
  local app_dir="$1"
  local public_config="$app_dir/.telz-public-build.json"
  local build_home="$BUILD_RELEASE_DIR/.build-home"
  local python_bootstrap
  local unit_name="telz-release-build-${BUILD_RELEASE_COMMIT:0:12}-$$"
  python_bootstrap="$(command -v python3.12 || true)"
  [[ -x "$python_bootstrap" ]] || die "python3.12 obrigatorio para construir a release"
  [[ "$build_home" == "$RELEASES_DIR/$BUILD_RELEASE_COMMIT/.build-home" ]] || die "home efemero do builder fora da release"
  [[ ! -e "$build_home" && ! -L "$build_home" ]] || die "home efemero do builder ja existe"
  if pgrep -u "$BUILD_USER" >/dev/null 2>&1; then
    die "builder possui processo anterior ao build"
  fi
  install -d -m 0700 -o "$BUILD_USER" -g "$BUILD_GROUP" "$build_home"
  prepare_public_build_config "$public_config"
  chown "$BUILD_USER:$BUILD_GROUP" "$public_config"
  chmod 0400 "$public_config"
  /usr/bin/systemd-run --wait --pipe --collect --quiet --service-type=exec \
    --unit="$unit_name" \
    --property="User=$BUILD_USER" \
    --property="Group=$BUILD_GROUP" \
    --property="WorkingDirectory=$app_dir" \
    --property="ReadWritePaths=$app_dir $build_home" \
    --property="ReadOnlyPaths=$BUNDLE_BUILD $DEPENDENCY_DIR" \
    --property="InaccessiblePaths=$INSTALL_DIR" \
    --property=ProtectSystem=strict \
    --property=ProtectHome=yes \
    --property=PrivateTmp=yes \
    --property=PrivateDevices=yes \
    --property=NoNewPrivileges=yes \
    --property=ProtectKernelTunables=yes \
    --property=ProtectKernelModules=yes \
    --property=ProtectControlGroups=yes \
    --property=RestrictSUIDSGID=yes \
    --property=LockPersonality=yes \
    --property=IPAddressDeny=any \
    --property=RestrictAddressFamilies=AF_UNIX \
    --property=KillMode=control-group \
    --property=TimeoutStartSec=30min \
    --setenv="HOME=$build_home" \
    --setenv="PATH=/usr/local/bin:/usr/bin:/bin" \
    "$BUNDLE_BUILD" "$app_dir" "$public_config" "$RUN_TESTS" "$python_bootstrap" "$DEPENDENCY_DIR"
  if pgrep -u "$BUILD_USER" >/dev/null 2>&1; then
    die "builder deixou processo persistente"
  fi
  chown -hR root:root "$build_home"
  rm -rf -- "$build_home"
}

alembic_at() {
  local code_dir="$1"
  shift
  as_service env TELZ_PROJECT_ROOT="$INSTALL_DIR" bash -c \
    'cd "$1" && shift && exec .venv/bin/alembic -c backend/alembic.ini "$@"' \
    bash "$code_dir" "$@"
}

database_current_at() {
  local code_dir="$1"
  as_service env TELZ_PROJECT_ROOT="$INSTALL_DIR" bash -c \
    'cd "$1" && exec .venv/bin/python -' bash "$code_dir" <<'PY'
import re

try:
    from sqlalchemy import text
    from backend.database import engine

    with engine.connect() as connection:
        rows = connection.execute(text("SELECT version_num FROM alembic_version ORDER BY version_num")).scalars().all()
    if len(rows) != 1 or not re.fullmatch(r"[A-Za-z0-9_]+", str(rows[0])):
        raise ValueError("revision invalida")
    print(rows[0])
except Exception:
    raise SystemExit("nao foi possivel consultar a revision atual do banco") from None
finally:
    if "engine" in globals():
        engine.dispose()
PY
}

schema_is_rollback_compatible() {
  local code_revision="$1"
  local database_revision="$2"
  [[ "$code_revision" == "$database_revision" ]] && return 0
  [[ "$code_revision:$database_revision" == "20260816_master_completion:20260818_platform_operations" ]] && return 0
  [[ "$code_revision:$database_revision" == "20260817_platform_wave0:20260818_platform_operations" ]]
}

validate_release_tree() {
  local app_dir="$1"
  local expected_commit="$2"
  local expected_revision="$3"
  local expected_dependency_sha="${4:-}"
  local allow_building="${5:-false}"
  local release_dir
  [[ "$expected_commit" =~ ^[0-9a-f]{40}$ ]] || die "commit esperado da release invalido"
  [[ "$app_dir" == "$RELEASES_DIR/$expected_commit/app" ]] || die "release diverge do caminho canonico"
  [[ "$allow_building" == "true" || "$allow_building" == "false" ]] || die "estado building invalido"
  release_dir="$(dirname "$app_dir")"
  if [[ "$allow_building" == "true" ]]; then
    require_root_owned_file "$release_dir/.building"
  else
    [[ ! -e "$release_dir/.building" && ! -L "$release_dir/.building" ]] || die "release final conserva marcador de build"
  fi
  [[ -d "$app_dir" && ! -L "$app_dir" && "$(realpath -e "$app_dir")" == "$app_dir" ]] || \
    die "release fora do layout aprovado: $app_dir"
  [[ -d "$release_dir" && ! -L "$release_dir" && "$(stat -c '%U' "$release_dir")" == "root" ]] || \
    die "diretorio pai da release deve ser root-owned e real"
  [[ -z "$(find "$release_dir" -maxdepth 0 -perm /022 -print -quit)" ]] || \
    die "diretorio pai da release nao pode ser gravavel por grupo/outros"
  [[ -z "$(find "$app_dir" -xdev ! -user root -print -quit)" ]] || die "release deve pertencer integralmente a root"
  [[ -z "$(find "$app_dir" -xdev \( -type d -o -type f \) -perm /022 -print -quit)" ]] || \
    die "release imutavel possui escrita de grupo/outros"
  [[ -z "$(find "$app_dir" -xdev ! -type d ! -type f ! -type l -print -quit)" ]] || die "release contem tipo especial"
  require_root_owned_file "$app_dir/.telz-release.json"
  /usr/bin/python3 - "$app_dir" "$expected_commit" "$expected_revision" "$expected_dependency_sha" "$SERVICE_USER" <<'PY'
import hashlib
import json
import os
import pwd
import re
import stat
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve(strict=True)
expected_commit, expected_revision = sys.argv[2], sys.argv[3]
expected_dependency_sha, service_user = sys.argv[4], sys.argv[5]
data = json.loads((root / ".telz-release.json").read_text(encoding="utf-8"))
if data.get("schema_version") != 2 or data.get("status") != "validated":
    raise SystemExit("manifest de release invalido")
if data.get("git_commit") != expected_commit or data.get("alembic_revision") != expected_revision:
    raise SystemExit("manifest de release diverge do target")
if expected_dependency_sha and data.get("dependency_artifact_sha256") != expected_dependency_sha:
    raise SystemExit("release cache usa artefato de dependencias diferente")
if not re.fullmatch(r"[0-9a-f]{40}", expected_commit):
    raise SystemExit("commit de release invalido")
if not re.fullmatch(r"[0-9a-f]{64}", str(data.get("dependency_artifact_sha256") or "")):
    raise SystemExit("digest de dependencias invalido")
build = json.loads((root / ".telz-build-metadata.json").read_text(encoding="utf-8"))
if build.get("schema_version") != 1 or build.get("commit") != expected_commit:
    raise SystemExit("metadata do build invalida")
file_digests = {
    "python_freeze_sha256": hashlib.sha256((root / ".telz-python-freeze.txt").read_bytes()).hexdigest(),
    "requirements_sha256": hashlib.sha256((root / "backend" / "requirements.txt").read_bytes()).hexdigest(),
    "pnpm_lock_sha256": hashlib.sha256((root / "pnpm-lock.yaml").read_bytes()).hexdigest(),
}
for key, actual in file_digests.items():
    if data.get(key) != actual or build.get(key) != actual:
        raise SystemExit("digest de dependencia da release divergiu")
if data.get("public_build_config_sha256") != build.get("public_build_config_sha256") or not re.fullmatch(
    r"[0-9a-f]{64}", str(data.get("public_build_config_sha256") or "")
):
    raise SystemExit("digest da configuracao publica divergiu")
toolchain = data.get("toolchain")
if toolchain != build.get("toolchain") or not isinstance(toolchain, dict):
    raise SystemExit("toolchain da release divergiu")
if not str(toolchain.get("python", "")).startswith("Python 3.12.") or toolchain.get("pip") != "25.1.1":
    raise SystemExit("toolchain Python invalida")
if not str(toolchain.get("node", "")).startswith("v22.") or toolchain.get("pnpm") != "10.14.0":
    raise SystemExit("toolchain Node invalida")
legacy_compat = data.get("legacy_compat") or {}
if not isinstance(legacy_compat, dict):
    raise SystemExit("mapa de compatibilidade legado invalido")
allowed_external = {}
if legacy_compat:
    if expected_commit != "2f1006860b648cf7a4734222da69879256c174e7":
        raise SystemExit("legacy_compat permitido somente para o commit auditado")
    expected_map = {"backend/.env": "/opt/telz/backend/.env"}
    if legacy_compat != expected_map:
        raise SystemExit("mapa legado diverge do adaptador auditado")
    allowed_external = {root / key: Path(value) for key, value in expected_map.items()}
elif expected_commit == "2f1006860b648cf7a4734222da69879256c174e7":
    raise SystemExit("release legada sem adaptador manifestado")
for current, directories, files in os.walk(root, followlinks=False):
    for name in [*directories, *files]:
        candidate = Path(current) / name
        if not candidate.is_symlink():
            continue
        resolved = candidate.resolve(strict=True)
        try:
            resolved.relative_to(root)
        except ValueError:
            allowed_target = allowed_external.get(candidate)
            if allowed_target is None:
                raise SystemExit(f"symlink escapa da release: {candidate}")
            if os.readlink(candidate) != str(allowed_target) or resolved != allowed_target.resolve(strict=True):
                raise SystemExit(f"link persistente legado divergiu: {candidate}")
            target_stat = allowed_target.lstat()
            if stat.S_ISLNK(target_stat.st_mode) or not stat.S_ISREG(target_stat.st_mode):
                raise SystemExit("destino persistente legado possui tipo invalido")
            if target_stat.st_uid != pwd.getpwnam(service_user).pw_uid or target_stat.st_mode & 0o022:
                raise SystemExit("destino persistente legado possui ownership ou modo inseguro")

digest = hashlib.sha256()
for candidate in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
    relative = candidate.relative_to(root).as_posix()
    if relative == ".telz-release.json":
        continue
    metadata = candidate.lstat()
    if stat.S_ISDIR(metadata.st_mode):
        kind, payload = "d", b""
    elif stat.S_ISREG(metadata.st_mode):
        kind, payload = "f", candidate.read_bytes()
    elif stat.S_ISLNK(metadata.st_mode):
        kind, payload = "l", os.readlink(candidate).encode("utf-8")
    else:
        raise SystemExit("tipo inesperado durante digest")
    digest.update(f"{kind}\0{relative}\0{stat.S_IMODE(metadata.st_mode):04o}\0".encode("utf-8"))
    digest.update(hashlib.sha256(payload).digest())
if data.get("content_sha256") != digest.hexdigest():
    raise SystemExit("digest de conteudo da release divergiu")
PY
}

validate_runtime_artifacts() {
  local app_dir="$1"
  [[ -x "$app_dir/.venv/bin/uvicorn" && -x "$app_dir/.venv/bin/alembic" ]] || die "release sem executaveis Python"
  [[ "$(head -n 1 "$app_dir/.venv/bin/uvicorn")" == "#!$app_dir/.venv/bin/python" ]] || die "shebang do uvicorn nao canonico"
  [[ "$(head -n 1 "$app_dir/.venv/bin/alembic")" == "#!$app_dir/.venv/bin/python" ]] || die "shebang do Alembic nao canonico"
  [[ -f "$app_dir/dist/server/node-build.mjs" ]] || die "release sem servidor web compilado"
  [[ -f "$app_dir/dist/spa/index.html" ]] || die "release sem SPA compilada"
  [[ -f "$app_dir/server/whatsapp-gateway-runtime.mjs" ]] || die "release sem runtime do gateway"
  [[ -d "$app_dir/uploads" && ! -L "$app_dir/uploads" ]] || die "release sem alvo real para bind de uploads"
  as_service node --check "$app_dir/server/whatsapp-gateway-runtime.mjs"
}

release_content_sha256() {
  /usr/bin/python3 - "$1" <<'PY'
import hashlib
import os
import stat
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve(strict=True)
digest = hashlib.sha256()
for candidate in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
    relative = candidate.relative_to(root).as_posix()
    if relative == ".telz-release.json":
        continue
    metadata = candidate.lstat()
    if stat.S_ISDIR(metadata.st_mode):
        kind, payload = "d", b""
    elif stat.S_ISREG(metadata.st_mode):
        kind, payload = "f", candidate.read_bytes()
    elif stat.S_ISLNK(metadata.st_mode):
        kind, payload = "l", os.readlink(candidate).encode("utf-8")
    else:
        raise SystemExit("tipo inesperado durante digest")
    digest.update(f"{kind}\0{relative}\0{stat.S_IMODE(metadata.st_mode):04o}\0".encode("utf-8"))
    digest.update(hashlib.sha256(payload).digest())
print(digest.hexdigest())
PY
}

write_release_manifest() {
  local app_dir="$1"
  local commit="$2"
  local revision="$3"
  local legacy_compat="$4"
  local content_sha
  content_sha="$(release_content_sha256 "$app_dir")"
  /usr/bin/python3 - "$app_dir/.telz-release.json" "$commit" "$revision" "$legacy_compat" \
    "$DEPENDENCY_ARCHIVE_SHA256" "$content_sha" "$app_dir/.telz-build-metadata.json" <<'PY'
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

target = Path(sys.argv[1])
legacy = {"backend/.env": "/opt/telz/backend/.env"} if sys.argv[4] == "true" else {}
build = json.loads(Path(sys.argv[7]).read_text(encoding="utf-8"))
if build.get("schema_version") != 1 or build.get("commit") != sys.argv[2]:
    raise SystemExit("metadata do build invalida")
for key in ("python_freeze_sha256", "requirements_sha256", "pnpm_lock_sha256", "public_build_config_sha256"):
    if not re.fullmatch(r"[0-9a-f]{64}", str(build.get(key) or "")):
        raise SystemExit("digest do build invalido")
if not isinstance(build.get("toolchain"), dict):
    raise SystemExit("toolchain do build invalida")
payload = {
    "schema_version": 2,
    "git_commit": sys.argv[2],
    "alembic_revision": sys.argv[3],
    "status": "validated",
    "legacy_compat": legacy,
    "dependency_artifact_sha256": sys.argv[5],
    "content_sha256": sys.argv[6],
    "python_freeze_sha256": build["python_freeze_sha256"],
    "requirements_sha256": build["requirements_sha256"],
    "pnpm_lock_sha256": build["pnpm_lock_sha256"],
    "public_build_config_sha256": build["public_build_config_sha256"],
    "toolchain": build["toolchain"],
    "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
}
descriptor, temporary_name = tempfile.mkstemp(prefix=".telz-release.", suffix=".tmp", dir=target.parent)
try:
    os.fchmod(descriptor, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8", closefd=True) as output:
        descriptor = -1
        output.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary_name, target)
    directory_fd = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
finally:
    if descriptor >= 0:
        os.close(descriptor)
    try:
        os.unlink(temporary_name)
    except FileNotFoundError:
        pass
PY
  chown root:root "$app_dir/.telz-release.json"
  chmod 0444 "$app_dir/.telz-release.json"
}

read_release_manifest() {
  local app_dir="$1"
  /usr/bin/python3 - "$app_dir/.telz-release.json" <<'PY'
import json
import re
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
commit = str(data.get("git_commit") or "")
revision = str(data.get("alembic_revision") or "")
if data.get("schema_version") != 2 or data.get("status") != "validated":
    raise SystemExit("manifest invalido")
if not re.fullmatch(r"[0-9a-f]{40}", commit) or not re.fullmatch(r"[A-Za-z0-9_]+", revision):
    raise SystemExit("identificadores invalidos")
print(commit)
print(revision)
PY
}

discard_partial_release() {
  [[ "${BUILD_RELEASE_COMMIT:-}" =~ ^[0-9a-f]{40}$ ]] || return 1
  [[ "${BUILD_RELEASE_DIR:-}" == "$RELEASES_DIR/$BUILD_RELEASE_COMMIT" ]] || return 1
  [[ "${BUILD_RELEASE_APP:-}" == "$BUILD_RELEASE_DIR/app" ]] || return 1
  [[ -d "$BUILD_RELEASE_DIR" && ! -L "$BUILD_RELEASE_DIR" ]] || return 1
  [[ "$(stat -c '%U' "$BUILD_RELEASE_DIR")" == "root" ]] || return 1
  [[ -f "$BUILD_RELEASE_DIR/.building" && ! -L "$BUILD_RELEASE_DIR/.building" ]] || return 1
  [[ "$(stat -c '%U' "$BUILD_RELEASE_DIR/.building")" == "root" ]] || return 1
  if [[ -L "$CURRENT_LINK" && "$(realpath -e "$CURRENT_LINK")" == "$BUILD_RELEASE_APP" ]]; then
    return 1
  fi
  rm -rf -- "$BUILD_RELEASE_DIR"
  BUILD_IN_PROGRESS=false
  BUILD_RELEASE_DIR=""
  BUILD_RELEASE_APP=""
  BUILD_RELEASE_COMMIT=""
}

validate_release_compatibility() {
  local release_app="$1"
  local release_revision="$2"
  local expected_database_revision="$3"
  local -a release_heads release_currents
  validate_runtime_artifacts "$release_app"
  mapfile -t release_heads < <(alembic_at "$release_app" heads | awk 'NF {print $1}')
  [[ "${#release_heads[@]}" -eq 1 && "${release_heads[0]}" == "$release_revision" ]] || \
    die "release diverge da revision esperada"
  mapfile -t release_currents < <(database_current_at "$release_app")
  [[ "${#release_currents[@]}" -eq 1 && "${release_currents[0]}" == "$expected_database_revision" ]] || \
    die "release nao acessa a revision atual do banco"
  as_service env TELZ_PROJECT_ROOT="$INSTALL_DIR" bash -c \
    'cd "$1" && exec .venv/bin/python -c "from backend.config import get_settings; settings = get_settings(); assert settings.DATABASE_URL"' \
    bash "$release_app"
}

materialize_release() {
  local release_commit="$1"
  local release_revision="$2"
  local source_archive="$3"
  local legacy_compat="$4"
  local expected_database_revision="$5"
  local release_dir="$RELEASES_DIR/$release_commit"
  local release_app="$release_dir/app"

  [[ "$release_commit" =~ ^[0-9a-f]{40}$ ]] || die "commit da release invalido"
  [[ "$release_revision" =~ ^[A-Za-z0-9_]+$ ]] || die "revision da release invalida"
  [[ "$legacy_compat" == "true" || "$legacy_compat" == "false" ]] || die "compatibilidade legada invalida"
  if [[ "$legacy_compat" == "true" ]]; then
    [[ "$release_commit" == "2f1006860b648cf7a4734222da69879256c174e7" ]] || die "adaptador legado fora do commit auditado"
  fi

  BUILD_RELEASE_COMMIT="$release_commit"
  BUILD_RELEASE_DIR="$release_dir"
  BUILD_RELEASE_APP="$release_app"
  if [[ -e "$release_dir/.building" || -L "$release_dir/.building" ]]; then
    BUILD_IN_PROGRESS=true
    discard_partial_release || die "release parcial nao pode ser removida"
  fi
  if [[ -d "$release_dir" ]]; then
    validate_release_tree "$release_app" "$release_commit" "$release_revision" "$DEPENDENCY_ARCHIVE_SHA256" false
    validate_release_compatibility "$release_app" "$release_revision" "$expected_database_revision"
    BUILD_RELEASE_DIR=""
    BUILD_RELEASE_APP=""
    BUILD_RELEASE_COMMIT=""
    return 0
  fi

  BUILD_IN_PROGRESS=true
  install -d -m 0755 -o root -g root "$release_dir"
  install -m 0400 -o root -g root /dev/null "$release_dir/.building"
  install -d -m 0700 -o root -g root "$release_app"
  extract_source_archive "$source_archive" "$release_app"
  [[ ! -e "$release_app/backend/.env" && ! -L "$release_app/backend/.env" ]] || die "release contem env persistente indevido"
  [[ ! -e "$release_app/uploads" && ! -L "$release_app/uploads" ]] || die "release contem uploads persistentes indevidos"
  [[ ! -e "$release_app/.runtime" && ! -L "$release_app/.runtime" ]] || die "release contem runtime persistente indevido"
  install -d -m 0700 -o root -g root "$release_app/uploads"
  chown -hR "$BUILD_USER:$BUILD_GROUP" "$release_app"
  run_isolated_release_build "$release_app"

  chown -hR root:root "$release_app"
  [[ -z "$(find "$release_app" -xdev ! -user root -print -quit)" ]] || die "freeze encontrou ownership residual do builder"
  find "$release_app" -xdev -type d -exec chmod 0555 {} +
  find "$release_app" -xdev -type f -perm /111 -exec chmod 0555 {} +
  find "$release_app" -xdev -type f ! -perm /111 -exec chmod 0444 {} +
  if [[ "$legacy_compat" == "true" ]]; then
    [[ -f "$INSTALL_DIR/backend/.env" && ! -L "$INSTALL_DIR/backend/.env" ]] || die "env persistente legado invalido"
    ln -s "$INSTALL_DIR/backend/.env" "$release_app/backend/.env"
    chown -h root:root "$release_app/backend/.env"
  fi
  write_release_manifest "$release_app" "$release_commit" "$release_revision" "$legacy_compat"
  chmod 0555 "$release_dir"
  validate_release_tree "$release_app" "$release_commit" "$release_revision" "$DEPENDENCY_ARCHIVE_SHA256" true
  validate_release_compatibility "$release_app" "$release_revision" "$expected_database_revision"
  rm -f -- "$release_dir/.building"
  BUILD_IN_PROGRESS=false
  BUILD_RELEASE_DIR=""
  BUILD_RELEASE_APP=""
  BUILD_RELEASE_COMMIT=""
  validate_release_tree "$release_app" "$release_commit" "$release_revision" "$DEPENDENCY_ARCHIVE_SHA256" false
}

materialize_rollback_release() {
  local legacy_compat=false
  [[ "$1" == "2f1006860b648cf7a4734222da69879256c174e7" ]] && legacy_compat=true
  materialize_release "$1" "$2" "$PREVIOUS_SOURCE_ARCHIVE" "$legacy_compat" "$DATABASE_CURRENT"
}

SOURCE_PREVIOUS_COMMIT=""
PREVIOUS_ACTIVE_COMMIT=""
PREVIOUS_ACTIVE_REVISION=""
PREVIOUS_CURRENT_TARGET=""
DATABASE_CURRENT=""
FINAL_RELEASE_DIR="$RELEASES_DIR/$EXPECTED_COMMIT"
FINAL_APP_DIR="$FINAL_RELEASE_DIR/app"
BUILD_IN_PROGRESS=false
BUILD_RELEASE_DIR=""
BUILD_RELEASE_APP=""
BUILD_RELEASE_COMMIT=""
UNIT_STAGE_DIR=""
OPERATIONS_STATE_DIR=""
CODE_CHANGED=false
CURRENT_SWAPPED=false
OPERATIONS_CHANGED=false
MAINTENANCE_WINDOW=false
MIGRATION_APPLIED=false
RECOVERY_FAILED=false
RECOVERY_REQUIRED=false
API_WAS_ACTIVE="inactive"
WEB_WAS_ACTIVE="inactive"
GATEWAY_WAS_ACTIVE="inactive"
MONITOR_TIMER_WAS_ENABLED="disabled"
MONITOR_TIMER_WAS_ACTIVE="inactive"

OPERATIONS_PATHS=(
  "$UPDATE_COMMAND"
  "$BACKUP_COMMAND"
  "$HEALTH_COMMAND"
  "$COLLECTOR_COMMAND"
  "$RESTORE_COMMAND"
  "$ROLLBACK_COMMAND"
  "$SSL_COMMAND"
  /etc/systemd/system/telz-api.service
  /etc/systemd/system/telz-web.service
  /etc/systemd/system/telz-whatsapp-gateway.service
  /etc/systemd/system/telz-monitoring.service
  /etc/systemd/system/telz-monitoring.timer
  /etc/cron.d/telz-backup
)
OPERATIONS_KEYS=(
  update-telz backup-telz telz-health-check telz-monitoring-collector restore-telz rollback-telz telz-finish-ssl
  telz-api.service telz-web.service telz-whatsapp-gateway.service telz-monitoring.service telz-monitoring.timer telz-backup.cron
)

snapshot_operational_artifacts() {
  local index target key
  OPERATIONS_STATE_DIR="$(mktemp -d /tmp/telz-operations-state.XXXXXX)"
  chmod 0700 "$OPERATIONS_STATE_DIR"
  for index in "${!OPERATIONS_PATHS[@]}"; do
    target="${OPERATIONS_PATHS[$index]}"
    key="${OPERATIONS_KEYS[$index]}"
    [[ ! -L "$target" ]] || die "artefato operacional nao pode ser symlink: $target"
    if [[ -f "$target" ]]; then
      cp -p -- "$target" "$OPERATIONS_STATE_DIR/$key"
      printf 'present\n' > "$OPERATIONS_STATE_DIR/$key.state"
    else
      printf 'absent\n' > "$OPERATIONS_STATE_DIR/$key.state"
    fi
  done
  MONITOR_TIMER_WAS_ENABLED="$(systemctl is-enabled telz-monitoring.timer 2>/dev/null || true)"
  MONITOR_TIMER_WAS_ACTIVE="$(systemctl is-active telz-monitoring.timer 2>/dev/null || true)"
}

restore_operational_artifacts() {
  local index target key state temporary
  [[ -d "$OPERATIONS_STATE_DIR" ]] || return 0
  for index in "${!OPERATIONS_PATHS[@]}"; do
    target="${OPERATIONS_PATHS[$index]}"
    key="${OPERATIONS_KEYS[$index]}"
    state="$(<"$OPERATIONS_STATE_DIR/$key.state")"
    if [[ "$state" == "present" ]]; then
      temporary="$target.telz-restore-$$"
      cp -p -- "$OPERATIONS_STATE_DIR/$key" "$temporary" || return $?
      mv -Tf -- "$temporary" "$target" || return $?
    else
      rm -f -- "$target" || return $?
    fi
  done
  systemctl daemon-reload || return $?
  if [[ "$(<"$OPERATIONS_STATE_DIR/telz-monitoring.timer.state")" == "present" ]]; then
    if [[ "$MONITOR_TIMER_WAS_ENABLED" == "enabled" ]]; then
      systemctl enable telz-monitoring.timer >/dev/null || return $?
    else
      systemctl disable telz-monitoring.timer >/dev/null || return $?
    fi
    if [[ "$MONITOR_TIMER_WAS_ACTIVE" == "active" ]]; then
      systemctl start telz-monitoring.timer || return $?
    else
      systemctl stop telz-monitoring.timer || return $?
    fi
  else
    if systemctl is-enabled telz-monitoring.timer >/dev/null 2>&1; then
      systemctl disable --now telz-monitoring.timer >/dev/null || return $?
    fi
    if systemctl list-unit-files telz-monitoring.service --no-legend 2>/dev/null | grep -q '^telz-monitoring.service'; then
      systemctl stop telz-monitoring.service || return $?
    fi
  fi
  OPERATIONS_CHANGED=false
}

unit_exists() {
  systemctl list-unit-files "$1.service" --no-legend 2>/dev/null | grep -q "^$1.service"
}

quiesce_services() {
  API_WAS_ACTIVE="$(systemctl is-active telz-api 2>/dev/null || true)"
  WEB_WAS_ACTIVE="$(systemctl is-active telz-web 2>/dev/null || true)"
  if unit_exists telz-whatsapp-gateway; then
    GATEWAY_WAS_ACTIVE="$(systemctl is-active telz-whatsapp-gateway 2>/dev/null || true)"
  fi
  MAINTENANCE_WINDOW=true
  if unit_exists telz-whatsapp-gateway; then
    systemctl stop telz-whatsapp-gateway
  fi
  systemctl stop telz-api telz-web
}

stop_services() {
  if unit_exists telz-whatsapp-gateway; then
    systemctl stop telz-whatsapp-gateway || return $?
  fi
  systemctl stop telz-api telz-web || return $?
  MAINTENANCE_WINDOW=true
}

start_new_services() {
  systemctl start telz-api telz-web
  if unit_exists telz-whatsapp-gateway; then
    systemctl start telz-whatsapp-gateway
  fi
}

restore_previous_service_state() {
  if [[ "$API_WAS_ACTIVE" == "active" ]]; then
    systemctl start telz-api || return $?
  else
    systemctl stop telz-api || return $?
  fi
  if [[ "$WEB_WAS_ACTIVE" == "active" ]]; then
    systemctl start telz-web || return $?
  else
    systemctl stop telz-web || return $?
  fi
  if unit_exists telz-whatsapp-gateway; then
    if [[ "$GATEWAY_WAS_ACTIVE" == "active" ]]; then
      systemctl start telz-whatsapp-gateway || return $?
    else
      systemctl stop telz-whatsapp-gateway || return $?
    fi
  fi
  MAINTENANCE_WINDOW=false
}

activate_release() {
  local temporary="$CURRENT_LINK.telz-new-$$"
  [[ ! -e "$temporary" && ! -L "$temporary" ]] || die "link temporario de release ja existe"
  ln -s "releases/$EXPECTED_COMMIT/app" "$temporary"
  chown -h root:root "$temporary"
  CURRENT_SWAPPED=true
  mv -Tf -- "$temporary" "$CURRENT_LINK"
}

restore_previous_release() {
  local temporary="$CURRENT_LINK.telz-restore-$$"
  if [[ -n "$PREVIOUS_CURRENT_TARGET" ]]; then
    ln -s "$PREVIOUS_CURRENT_TARGET" "$temporary" || return $?
    chown -h root:root "$temporary" || return $?
    mv -Tf -- "$temporary" "$CURRENT_LINK" || return $?
  else
    rm -f -- "$CURRENT_LINK" || return $?
  fi
  CURRENT_SWAPPED=false
}

rollback_source_code() {
  [[ "$CODE_CHANGED" == "true" ]] || return 0
  as_service git -C "$INSTALL_DIR" checkout --detach "$SOURCE_PREVIOUS_COMMIT" || return $?
  as_service git -C "$INSTALL_DIR" branch -f "$BRANCH" "$SOURCE_PREVIOUS_COMMIT" || return $?
  as_service git -C "$INSTALL_DIR" checkout "$BRANCH" || return $?
  CODE_CHANGED=false
}

health_recovered_release() {
  local recovered_code_dir="$INSTALL_DIR"
  local expected_revision
  if [[ -n "$PREVIOUS_CURRENT_TARGET" ]]; then
    recovered_code_dir="$PREVIOUS_CURRENT_TARGET"
  fi
  expected_revision="$(database_current_at "$recovered_code_dir")" || return $?
  [[ "$expected_revision" =~ ^[A-Za-z0-9_]+$ ]] || return 1
  TELZ_ALEMBIC_TARGET="$expected_revision" \
    TELZ_REQUIRE_PUBLIC_HTTPS="$REQUIRE_PUBLIC_HTTPS" \
    TELZ_PUBLIC_HEALTH_URL="$PUBLIC_HEALTH_URL" \
    "$HEALTH_COMMAND" "$INSTALL_DIR"
}

run_recovery_step() {
  local label="$1"
  shift
  local action="${1:-}"
  local recovery_rc
  set +e
  (
    set -Eeuo pipefail
    "$@"
  )
  recovery_rc=$?
  set -e
  if (( recovery_rc != 0 )); then
    echo "[update][erro] $label falhou (rc=$recovery_rc)" >&2
    RECOVERY_FAILED=true
  else
    case "$action" in
      stop_services) MAINTENANCE_WINDOW=true ;;
      restore_previous_release) CURRENT_SWAPPED=false ;;
      restore_operational_artifacts) OPERATIONS_CHANGED=false ;;
      rollback_source_code) CODE_CHANGED=false ;;
      restore_previous_service_state) MAINTENANCE_WINDOW=false ;;
    esac
  fi
  return 0
}

on_error() {
  local rc="${1:-1}"
  [[ "$rc" =~ ^[0-9]+$ ]] || rc=1
  ERROR_HANDLER_ARMED=false
  trap - ERR TERM INT HUP
  if [[ "$RECOVERY_REQUIRED" != "true" ]]; then
    exit "$rc"
  fi
  if [[ "$MAINTENANCE_WINDOW" == "true" ]]; then
    run_recovery_step "quiesce para recuperacao" stop_services
  fi
  if [[ "$CURRENT_SWAPPED" == "true" ]]; then
    run_recovery_step "restauracao da release ativa" restore_previous_release
  fi
  if [[ "$OPERATIONS_CHANGED" == "true" ]]; then
    run_recovery_step "restauracao de helpers e units" restore_operational_artifacts
  fi
  if [[ "$CODE_CHANGED" == "true" ]]; then
    run_recovery_step "restauracao do checkout fonte" rollback_source_code
  fi
  if [[ "$MAINTENANCE_WINDOW" == "true" && "$RECOVERY_FAILED" == "false" ]]; then
    run_recovery_step "restauracao dos servicos anteriores" restore_previous_service_state
  fi
  if [[ "$MAINTENANCE_WINDOW" == "false" && "$RECOVERY_FAILED" == "false" && -x "$HEALTH_COMMAND" ]]; then
    run_recovery_step "health da release recuperada" health_recovered_release
  fi
  if [[ "$RECOVERY_FAILED" == "true" ]]; then
    if ! stop_services; then
      echo "[update][erro] parada fail-closed dos servicos tambem falhou" >&2
    fi
    MAINTENANCE_WINDOW=true
    echo "[update][erro] recuperacao incompleta; servicos permanecem parados" >&2
  fi
  if [[ "$MIGRATION_APPLIED" == "true" ]]; then
    echo "[update][atencao] migration pode ter sido aplicada; nenhum downgrade automatico foi executado" >&2
  fi
  exit "$rc"
}
trap 'rc=$?; on_error "$rc"' ERR
trap 'on_error 143' TERM HUP
trap 'on_error 130' INT
ERROR_HANDLER_ARMED=true

cd "$INSTALL_DIR"
[[ -z "$(as_service git -C "$INSTALL_DIR" status --porcelain --untracked-files=all)" ]] || \
  die "worktree possui alteracoes ou arquivos nao rastreados"
CURRENT_BRANCH="$(as_service git -C "$INSTALL_DIR" symbolic-ref --quiet --short HEAD)" || die "checkout destacado nao permitido"
[[ "$CURRENT_BRANCH" == "$BRANCH" ]] || die "branch atual difere da branch aprovada"
SOURCE_PREVIOUS_COMMIT="$(as_service git -C "$INSTALL_DIR" rev-parse HEAD)"

ACTIVE_CODE_DIR="$INSTALL_DIR"
if [[ -e "$CURRENT_LINK" || -L "$CURRENT_LINK" ]]; then
  [[ -L "$CURRENT_LINK" && "$(stat -c '%U' "$CURRENT_LINK")" == "root" ]] || die "current deve ser symlink root-owned"
  PREVIOUS_CURRENT_TARGET="$(realpath -e "$CURRENT_LINK")"
  [[ "$PREVIOUS_CURRENT_TARGET" == "$RELEASES_DIR"/[0-9a-f][0-9a-f]*"/app" ]] || die "current aponta fora de releases"
  mapfile -t ACTIVE_MANIFEST < <(read_release_manifest "$PREVIOUS_CURRENT_TARGET")
  [[ "${#ACTIVE_MANIFEST[@]}" -eq 2 ]] || die "manifest ativo invalido"
  PREVIOUS_ACTIVE_COMMIT="${ACTIVE_MANIFEST[0]}"
  PREVIOUS_ACTIVE_REVISION="${ACTIVE_MANIFEST[1]}"
  validate_release_tree "$PREVIOUS_CURRENT_TARGET" "$PREVIOUS_ACTIVE_COMMIT" "$PREVIOUS_ACTIVE_REVISION"
  ACTIVE_CODE_DIR="$PREVIOUS_CURRENT_TARGET"
else
  [[ -x "$INSTALL_DIR/.venv/bin/alembic" ]] || die "Alembic legado ausente para o primeiro deploy"
  PREVIOUS_ACTIVE_COMMIT="$SOURCE_PREVIOUS_COMMIT"
  mapfile -t LEGACY_HEADS < <(alembic_at "$INSTALL_DIR" heads | awk 'NF {print $1}')
  [[ "${#LEGACY_HEADS[@]}" -eq 1 ]] || die "codigo legado deve possuir exatamente um head"
  PREVIOUS_ACTIVE_REVISION="${LEGACY_HEADS[0]}"
fi

mapfile -t DB_CURRENTS < <(database_current_at "$ACTIVE_CODE_DIR")
[[ "${#DB_CURRENTS[@]}" -eq 1 ]] || die "banco deve possuir exatamente uma revision atual"
DATABASE_CURRENT="${DB_CURRENTS[0]}"
echo "[update] revision atual do banco: $DATABASE_CURRENT"
schema_is_rollback_compatible "$PREVIOUS_ACTIVE_REVISION" "$DATABASE_CURRENT" || \
  die "release ativa ($PREVIOUS_ACTIVE_REVISION) nao e compativel com o banco ($DATABASE_CURRENT)"
[[ "$EXPECTED_PREVIOUS_COMMIT" == "$PREVIOUS_ACTIVE_COMMIT" ]] || die "commit anterior informado diverge da release ativa"
[[ "$SOURCE_PREVIOUS_COMMIT" == "$PREVIOUS_ACTIVE_COMMIT" ]] || die "checkout fonte diverge da release ativa"

as_service git -C "$INSTALL_DIR" fetch --prune origin "$BRANCH"
REMOTE_COMMIT="$(as_service git -C "$INSTALL_DIR" rev-parse --verify "origin/$BRANCH^{commit}")"
TARGET_COMMIT="$(as_service git -C "$INSTALL_DIR" rev-parse --verify "$EXPECTED_COMMIT^{commit}")"
[[ "$TARGET_COMMIT" == "$EXPECTED_COMMIT" ]] || die "SHA esperado nao resolveu exatamente"
as_service git -C "$INSTALL_DIR" merge-base --is-ancestor "$SOURCE_PREVIOUS_COMMIT" "$TARGET_COMMIT" || \
  die "SHA esperado nao e fast-forward do checkout fonte"
as_service git -C "$INSTALL_DIR" merge-base --is-ancestor "$TARGET_COMMIT" "$REMOTE_COMMIT" || \
  die "SHA esperado nao pertence a origin/$BRANCH"

[[ ! -L /var/lib/telz && ! -L "$RELEASES_DIR" ]] || die "raiz de releases nao pode ser symlink"
install -d -m 0755 -o root -g root /var/lib/telz "$RELEASES_DIR"
for release_parent in /var/lib/telz "$RELEASES_DIR"; do
  [[ -d "$release_parent" && ! -L "$release_parent" && "$(realpath -e "$release_parent")" == "$release_parent" ]] || \
    die "raiz de releases invalida: $release_parent"
  [[ "$(stat -c '%U' "$release_parent")" == "root" ]] || die "raiz de releases deve pertencer a root"
  [[ -z "$(find "$release_parent" -maxdepth 0 -perm /022 -print -quit)" ]] || \
    die "raiz de releases nao pode ser gravavel por grupo/outros"
done
SOURCE_ARCHIVE="$(require_source_archive "$SOURCE_ARCHIVE_INPUT" "$SOURCE_ARCHIVE_SHA256" "$EXPECTED_COMMIT")"
PREVIOUS_SOURCE_ARCHIVE="$(require_source_archive "$PREVIOUS_SOURCE_ARCHIVE_INPUT" "$PREVIOUS_SOURCE_ARCHIVE_SHA256" "$EXPECTED_PREVIOUS_COMMIT")"
DEPENDENCY_ARCHIVE="$(require_dependency_archive "$DEPENDENCY_ARCHIVE_INPUT" "$DEPENDENCY_ARCHIVE_SHA256")"
ensure_build_identity
materialize_dependencies
if [[ -z "$PREVIOUS_CURRENT_TARGET" ]]; then
  materialize_rollback_release "$SOURCE_PREVIOUS_COMMIT" "$PREVIOUS_ACTIVE_REVISION"
fi
materialize_release "$EXPECTED_COMMIT" "$ALEMBIC_TARGET" "$SOURCE_ARCHIVE" false "$DATABASE_CURRENT"

schema_is_rollback_compatible "$PREVIOUS_ACTIVE_REVISION" "$ALEMBIC_TARGET" || \
  die "migration para $ALEMBIC_TARGET nao permite retorno seguro a $PREVIOUS_ACTIVE_REVISION"

echo "[update] preflight completo da release ativa antes de qualquer mutacao"
TELZ_ALEMBIC_TARGET="$DATABASE_CURRENT" \
  TELZ_REQUIRE_PUBLIC_HTTPS="$REQUIRE_PUBLIC_HTTPS" \
  TELZ_PUBLIC_HEALTH_URL="$PUBLIC_HEALTH_URL" \
  "$BUNDLE_HEALTH" "$INSTALL_DIR"

snapshot_operational_artifacts
RECOVERY_REQUIRED=true
quiesce_services

echo "[update] criando backup coerente com os servicos quiescidos"
TELZ_MAINTENANCE_LOCK_HELD=true \
  TELZ_BACKUP_GIT_COMMIT_OVERRIDE="$PREVIOUS_ACTIVE_COMMIT" \
  TELZ_BACKUP_ALEMBIC_REVISION_OVERRIDE="$DATABASE_CURRENT" \
  TELZ_SERVICE_USER="$SERVICE_USER" \
  "$BUNDLE_BACKUP" "$INSTALL_DIR"

if [[ "$SOURCE_PREVIOUS_COMMIT" != "$EXPECTED_COMMIT" ]]; then
  CODE_CHANGED=true
  as_service git -C "$INSTALL_DIR" merge --ff-only "$EXPECTED_COMMIT"
fi
[[ "$(as_service git -C "$INSTALL_DIR" rev-parse HEAD)" == "$EXPECTED_COMMIT" ]] || die "checkout fonte nao convergiu"
[[ -z "$(as_service git -C "$INSTALL_DIR" status --porcelain --untracked-files=all)" ]] || die "checkout fonte ficou sujo"

if [[ "$DATABASE_CURRENT" != "$ALEMBIC_TARGET" ]]; then
  MIGRATION_APPLIED=true
  alembic_at "$FINAL_APP_DIR" upgrade "$ALEMBIC_TARGET"
fi
mapfile -t DEPLOYED_CURRENTS < <(database_current_at "$FINAL_APP_DIR")
[[ "${#DEPLOYED_CURRENTS[@]}" -eq 1 && "${DEPLOYED_CURRENTS[0]}" == "$ALEMBIC_TARGET" ]] || \
  die "banco nao convergiu para $ALEMBIC_TARGET"

activate_release
OPERATIONS_CHANGED=true
install -m 0755 -o root -g root "$BUNDLE_UPDATE" "$UPDATE_COMMAND"
install -m 0755 -o root -g root "$BUNDLE_BACKUP" "$BACKUP_COMMAND"
install -m 0755 -o root -g root "$BUNDLE_HEALTH" "$HEALTH_COMMAND"
install -m 0755 -o root -g root "$BUNDLE_COLLECTOR" "$COLLECTOR_COMMAND"
install -m 0755 -o root -g root "$BUNDLE_RESTORE" "$RESTORE_COMMAND"
install -m 0755 -o root -g root "$BUNDLE_ROLLBACK" "$ROLLBACK_COMMAND"
install -m 0755 -o root -g root "$BUNDLE_SSL" "$SSL_COMMAND"

UNIT_STAGE_DIR="$(mktemp -d /tmp/telz-unit-stage.XXXXXX)"
chmod 0700 "$UNIT_STAGE_DIR"
sed -e "s#__INSTALL_DIR__#$INSTALL_DIR#g" -e "s#__CODE_DIR__#$CURRENT_LINK#g" \
  -e "s#__SERVICE_USER__#$SERVICE_USER#g" -e "s#__API_PORT__#${TELZ_API_PORT:-8000}#g" \
  -e "s#__API_WORKERS__#${TELZ_API_WORKERS:-2}#g" \
  "$BUNDLE_API_UNIT" > "$UNIT_STAGE_DIR/telz-api.service"
sed -e "s#__INSTALL_DIR__#$INSTALL_DIR#g" -e "s#__CODE_DIR__#$CURRENT_LINK#g" \
  -e "s#__SERVICE_USER__#$SERVICE_USER#g" -e "s#__WEB_PORT__#${TELZ_WEB_PORT:-3000}#g" \
  "$BUNDLE_WEB_UNIT" > "$UNIT_STAGE_DIR/telz-web.service"
sed -e "s#__INSTALL_DIR__#$INSTALL_DIR#g" -e "s#__CODE_DIR__#$CURRENT_LINK#g" \
  -e "s#__SERVICE_USER__#$SERVICE_USER#g" -e "s#__WHATSAPP_GATEWAY_PORT__#${TELZ_WHATSAPP_GATEWAY_PORT:-3020}#g" \
  "$BUNDLE_GATEWAY_UNIT" > "$UNIT_STAGE_DIR/telz-whatsapp-gateway.service"
sed -e "s#__INSTALL_DIR__#$INSTALL_DIR#g" -e "s#__SERVICE_USER__#$SERVICE_USER#g" \
  -e "s#__API_PORT__#${TELZ_API_PORT:-8000}#g" -e "s#__WEB_PORT__#${TELZ_WEB_PORT:-3000}#g" \
  "$BUNDLE_MONITOR_UNIT" > "$UNIT_STAGE_DIR/telz-monitoring.service"
install -m 0644 -o root -g root "$BUNDLE_MONITOR_TIMER" "$UNIT_STAGE_DIR/telz-monitoring.timer"
chmod 0644 "$UNIT_STAGE_DIR"/*.service
systemd-analyze verify "$UNIT_STAGE_DIR"/*.service "$UNIT_STAGE_DIR/telz-monitoring.timer"
for unit_file in "$UNIT_STAGE_DIR"/*.service "$UNIT_STAGE_DIR/telz-monitoring.timer"; do
  install -m 0644 -o root -g root "$unit_file" "/etc/systemd/system/$(basename "$unit_file")"
done
cat > /etc/cron.d/telz-backup <<EOF
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
15 3 * * * root $BACKUP_COMMAND $INSTALL_DIR >/var/log/telz-backup.log 2>&1
EOF
chmod 0644 /etc/cron.d/telz-backup
install -d -m 0750 -o root -g "$SERVICE_USER" /var/lib/telz/monitoring
systemctl daemon-reload
systemctl enable telz-api telz-web telz-monitoring.timer
if unit_exists telz-whatsapp-gateway; then
  systemctl enable telz-whatsapp-gateway
fi
systemctl enable --now telz-monitoring.timer
start_new_services
systemctl start telz-monitoring.service

TELZ_ALEMBIC_TARGET="$ALEMBIC_TARGET" \
  TELZ_REQUIRE_PUBLIC_HTTPS="$REQUIRE_PUBLIC_HTTPS" \
  TELZ_PUBLIC_HEALTH_URL="$PUBLIC_HEALTH_URL" \
  "$HEALTH_COMMAND" "$INSTALL_DIR"

MAINTENANCE_WINDOW=false
RECOVERY_REQUIRED=false
CURRENT_SWAPPED=false
OPERATIONS_CHANGED=false
CODE_CHANGED=false
ERROR_HANDLER_ARMED=false
trap - ERR TERM INT HUP
echo "[update] concluido release=$EXPECTED_COMMIT revision=$ALEMBIC_TARGET current=$(readlink -f "$CURRENT_LINK")"
