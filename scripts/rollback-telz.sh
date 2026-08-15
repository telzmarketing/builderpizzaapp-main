#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

ERROR_HANDLER_ARMED=false

die() {
  echo "[rollback][erro] $*" >&2
  if [[ "${ERROR_HANDLER_ARMED:-false}" == "true" ]]; then
    on_error 1
  fi
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
[[ $# -eq 2 ]] || die "uso: rollback-telz.sh /opt/telz COMMIT"

INSTALL_INPUT="$1"
[[ "$INSTALL_INPUT" = /* && "$INSTALL_INPUT" != "/" && ! -L "$INSTALL_INPUT" ]] || die "INSTALL_DIR invalido"
INSTALL_DIR="$(realpath -e "$INSTALL_INPUT")"
REQUESTED_COMMIT="$2"
SERVICE_USER="${TELZ_SERVICE_USER:-telz}"
RELEASES_DIR="${TELZ_RELEASES_DIR:-/var/lib/telz/releases}"
CURRENT_LINK="${TELZ_CURRENT_RELEASE_LINK:-/var/lib/telz/current}"
REQUIRE_PUBLIC_HTTPS="${TELZ_REQUIRE_PUBLIC_HTTPS:-true}"
PUBLIC_HEALTH_URL="${TELZ_PUBLIC_HEALTH_URL:-}"
BACKUP_COMMAND="${TELZ_BACKUP_COMMAND:-/usr/local/bin/backup-telz}"
HEALTH_COMMAND="${TELZ_HEALTH_COMMAND:-/usr/local/sbin/telz-health-check}"
MAINTENANCE_LOCK_DIR="/run/lock/telz"
MAINTENANCE_LOCK="$MAINTENANCE_LOCK_DIR/maintenance.lock"

[[ "$REQUESTED_COMMIT" =~ ^[0-9a-f]{40}$ ]] || die "COMMIT deve ser um SHA-1 completo"
[[ "$REQUIRE_PUBLIC_HTTPS" == "true" || "$REQUIRE_PUBLIC_HTTPS" == "false" ]] || \
  die "TELZ_REQUIRE_PUBLIC_HTTPS deve ser true ou false"
[[ "${TELZ_MAINTENANCE_LOCK_HELD:-false}" == "false" ]] || \
  die "rollback nao aceita bypass do lock de manutencao"
[[ -f "$INSTALL_DIR/backend/.env" && ! -L "$INSTALL_DIR/backend/.env" ]] || die "backend/.env persistente invalido"
id "$SERVICE_USER" >/dev/null 2>&1 || die "usuario de servico inexistente: $SERVICE_USER"
require_root_owned_executable "$BACKUP_COMMAND"
require_root_owned_executable "$HEALTH_COMMAND"
command -v flock >/dev/null 2>&1 || die "flock nao encontrado"
[[ -x /usr/bin/python3 ]] || die "/usr/bin/python3 nao encontrado"

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

validate_release_path() {
  local release_app="$1"
  local releases_real release_real release_root release_id manifest candidate
  [[ -d "$RELEASES_DIR" && ! -L "$RELEASES_DIR" ]] || die "diretorio de releases invalido"
  releases_real="$(realpath -e "$RELEASES_DIR")"
  release_real="$(realpath -e "$release_app")"
  release_root="$(dirname "$release_real")"
  release_id="$(basename "$release_root")"
  [[ "$(dirname "$release_root")" == "$releases_real" && "$(basename "$release_real")" == "app" ]] || \
    die "release fora do layout aprovado"
  [[ "$release_id" =~ ^[0-9a-f]{40}$ ]] || die "identificador da release invalido"
  manifest="$release_real/.telz-release.json"
  for candidate in "$releases_real" "$release_root" "$release_real" "$manifest"; do
    [[ -e "$candidate" && ! -L "$candidate" ]] || die "release possui componente inseguro: $candidate"
    [[ "$(stat -c '%U' "$candidate")" == "root" ]] || die "release deve pertencer a root: $candidate"
    [[ -z "$(find "$candidate" -maxdepth 0 -perm /022 -print -quit)" ]] || \
      die "release gravavel por grupo/outros: $candidate"
  done
  [[ -z "$(find "$release_real" -xdev ! -user root -print -quit)" ]] || \
    die "release deve pertencer integralmente a root"
  [[ -z "$(find "$release_real" -xdev \( -type d -o -type f \) -perm /022 -print -quit)" ]] || \
    die "release imutavel possui escrita de grupo/outros"
  [[ -z "$(find "$release_real" -xdev ! -type d ! -type f ! -type l -print -quit)" ]] || \
    die "release contem tipo especial"
  printf '%s\n' "$release_real"
}

read_release_manifest() {
  local app_dir="$1"
  /usr/bin/python3 - "$app_dir/.telz-release.json" "$(basename "$(dirname "$app_dir")")" "$INSTALL_DIR" "$SERVICE_USER" <<'PY'
import hashlib
import json
import os
import pwd
import re
import stat
import sys
from pathlib import Path

manifest_path = Path(sys.argv[1])
root = manifest_path.parent.resolve(strict=True)
data = json.loads(manifest_path.read_text(encoding="utf-8"))
commit = str(data.get("git_commit") or "")
revision = str(data.get("alembic_revision") or "")
if data.get("schema_version") != 2 or data.get("status") != "validated":
    raise SystemExit("manifest da release nao validado")
if commit != sys.argv[2] or not re.fullmatch(r"[0-9a-f]{40}", commit):
    raise SystemExit("commit da release invalido")
if not re.fullmatch(r"[A-Za-z0-9_]+", revision):
    raise SystemExit("revision da release invalida")
hash_fields = ("dependency_artifact_sha256", "content_sha256", "python_freeze_sha256", "requirements_sha256", "pnpm_lock_sha256", "public_build_config_sha256")
if any(not re.fullmatch(r"[0-9a-f]{64}", str(data.get(name) or "")) for name in hash_fields):
    raise SystemExit("hash do manifest da release invalido")
toolchain = data.get("toolchain")
if not isinstance(toolchain, dict) or set(toolchain) != {"python", "pip", "node", "pnpm"} or not all(isinstance(value, str) and value for value in toolchain.values()):
    raise SystemExit("toolchain do manifest da release invalida")
expected_legacy = {"backend/.env": str(Path(sys.argv[3]) / "backend" / ".env")} if commit == "2f1006860b648cf7a4734222da69879256c174e7" else {}
if data.get("legacy_compat") != expected_legacy:
    raise SystemExit("legacy_compat do manifest invalido")
allowed_external = {root / key: Path(value) for key, value in expected_legacy.items()}
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
            if allowed_target is None or os.readlink(candidate) != str(allowed_target):
                raise SystemExit("release possui symlink externo nao autorizado")
            if resolved != allowed_target.resolve(strict=True):
                raise SystemExit("symlink persistente legado divergiu")
            target_stat = allowed_target.lstat()
            if not stat.S_ISREG(target_stat.st_mode) or target_stat.st_uid != pwd.getpwnam(sys.argv[4]).pw_uid:
                raise SystemExit("destino persistente legado inseguro")
            if target_stat.st_mode & 0o022:
                raise SystemExit("destino persistente legado gravavel")
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
        raise SystemExit("tipo inesperado durante digest da release")
    digest.update(f"{kind}\0{relative}\0{stat.S_IMODE(metadata.st_mode):04o}\0".encode("utf-8"))
    digest.update(hashlib.sha256(payload).digest())
if data.get("content_sha256") != digest.hexdigest():
    raise SystemExit("digest de conteudo da release divergiu")
print(commit)
print(revision)
PY
}

alembic_at() {
  local code_dir="$1"
  shift
  sudo -u "$SERVICE_USER" -H env TELZ_PROJECT_ROOT="$INSTALL_DIR" bash -c \
    'cd "$1" && shift && exec .venv/bin/alembic -c backend/alembic.ini "$@"' \
    bash "$code_dir" "$@"
}

database_revisions_at() {
  local code_dir="$1"
  sudo -u "$SERVICE_USER" -H env TELZ_PROJECT_ROOT="$INSTALL_DIR" \
    "$code_dir/.venv/bin/python" - "$code_dir" <<'PY'
import os
import re
import sys

try:
    os.chdir(sys.argv[1])
    sys.path.insert(0, sys.argv[1])
    from sqlalchemy import text
    from backend.database import engine
    with engine.connect() as connection:
        values = [str(row[0]) for row in connection.execute(text("SELECT version_num FROM alembic_version"))]
except Exception:
    raise SystemExit("consulta segura da revision falhou")
if len(values) != 1 or not re.fullmatch(r"[A-Za-z0-9_]+", values[0]):
    raise SystemExit("banco deve possuir exatamente uma revision valida")
print(values[0])
PY
}

schema_pair_is_compatible() {
  [[ "$1" == "$2" ]] || \
    [[ "$1:$2" == "20260816_master_completion:20260818_platform_operations" ]] || \
    [[ "$1:$2" == "20260817_platform_wave0:20260818_platform_operations" ]]
}

[[ -L "$CURRENT_LINK" && "$(stat -c '%U' "$CURRENT_LINK")" == "root" ]] || \
  die "rollback por release exige current root-owned"
ORIGINAL_CODE_DIR="$(validate_release_path "$CURRENT_LINK")"
TARGET_CODE_DIR="$(validate_release_path "$RELEASES_DIR/$REQUESTED_COMMIT/app")"
readarray -t ORIGINAL_MANIFEST < <(read_release_manifest "$ORIGINAL_CODE_DIR")
readarray -t TARGET_MANIFEST < <(read_release_manifest "$TARGET_CODE_DIR")
[[ "${#ORIGINAL_MANIFEST[@]}" -eq 2 && "${#TARGET_MANIFEST[@]}" -eq 2 ]] || die "manifest de release invalido"
ORIGINAL_COMMIT="${ORIGINAL_MANIFEST[0]}"
ORIGINAL_REVISION="${ORIGINAL_MANIFEST[1]}"
TARGET_COMMIT="${TARGET_MANIFEST[0]}"
TARGET_REVISION="${TARGET_MANIFEST[1]}"
[[ "$TARGET_COMMIT" == "$REQUESTED_COMMIT" ]] || die "release alvo diverge do commit solicitado"
[[ "$TARGET_COMMIT" != "$ORIGINAL_COMMIT" ]] || die "release alvo ja esta ativa"

mapfile -t ORIGINAL_HEADS < <(alembic_at "$ORIGINAL_CODE_DIR" heads | awk 'NF {print $1}')
mapfile -t TARGET_HEADS < <(alembic_at "$TARGET_CODE_DIR" heads | awk 'NF {print $1}')
mapfile -t DB_CURRENTS < <(database_revisions_at "$ORIGINAL_CODE_DIR")
[[ "${#ORIGINAL_HEADS[@]}" -eq 1 && "${ORIGINAL_HEADS[0]}" == "$ORIGINAL_REVISION" ]] || \
  die "head da release atual diverge do manifest"
[[ "${#TARGET_HEADS[@]}" -eq 1 && "${TARGET_HEADS[0]}" == "$TARGET_REVISION" ]] || \
  die "head da release alvo diverge do manifest"
[[ "${#DB_CURRENTS[@]}" -eq 1 ]] || die "banco deve possuir exatamente uma revision atual"
DATABASE_REVISION="${DB_CURRENTS[0]}"
schema_pair_is_compatible "$ORIGINAL_REVISION" "$DATABASE_REVISION" || \
  die "release atual nao e compativel com o banco"
schema_pair_is_compatible "$TARGET_REVISION" "$DATABASE_REVISION" || \
  die "release alvo nao e compativel com o banco; nenhum downgrade automatico sera executado"

EXPECTED_CONFIRMATION="ROLLBACK ${TARGET_COMMIT:0:12}"
ANSWER="${TELZ_ROLLBACK_CONFIRM:-}"
if [[ -z "$ANSWER" ]]; then
  echo "[rollback] release: ${ORIGINAL_COMMIT:0:12} -> ${TARGET_COMMIT:0:12}"
  echo "[rollback] schema sera preservado em $DATABASE_REVISION; nenhuma migration sera revertida."
  read -r -p "Digite '$EXPECTED_CONFIRMATION' para continuar: " ANSWER
fi
[[ "$ANSWER" == "$EXPECTED_CONFIRMATION" ]] || die "confirmacao invalida"

echo "[rollback] criando backup validado antes da troca atomica"
TELZ_MAINTENANCE_LOCK_HELD=true \
  TELZ_BACKUP_GIT_COMMIT_OVERRIDE="$ORIGINAL_COMMIT" \
  TELZ_BACKUP_ALEMBIC_REVISION_OVERRIDE="$DATABASE_REVISION" \
  TELZ_SERVICE_USER="$SERVICE_USER" \
  "$BACKUP_COMMAND" "$INSTALL_DIR"

unit_exists() {
  systemctl list-unit-files "$1.service" --no-legend 2>/dev/null | grep -q "^$1.service"
}

API_WAS_ACTIVE="$(systemctl is-active telz-api 2>/dev/null || true)"
WEB_WAS_ACTIVE="$(systemctl is-active telz-web 2>/dev/null || true)"
GATEWAY_WAS_ACTIVE="inactive"
if unit_exists telz-whatsapp-gateway; then
  GATEWAY_WAS_ACTIVE="$(systemctl is-active telz-whatsapp-gateway 2>/dev/null || true)"
fi
[[ "$API_WAS_ACTIVE" == "active" && "$WEB_WAS_ACTIVE" == "active" ]] || \
  die "telz-api e telz-web devem estar ativos antes do rollback"

SERVICES_TOUCHED=false
CURRENT_SWAPPED=false
RECOVERY_FAILED=false

stop_services() {
  if unit_exists telz-whatsapp-gateway; then
    systemctl stop telz-whatsapp-gateway
  fi
  systemctl stop telz-api telz-web
  SERVICES_TOUCHED=true
}

start_target_services() {
  systemctl start telz-api telz-web
  if unit_exists telz-whatsapp-gateway; then
    systemctl start telz-whatsapp-gateway
  fi
  SERVICES_TOUCHED=false
}

restore_service_state() {
  if [[ "$API_WAS_ACTIVE" == "active" ]]; then systemctl start telz-api; else systemctl stop telz-api; fi
  if [[ "$WEB_WAS_ACTIVE" == "active" ]]; then systemctl start telz-web; else systemctl stop telz-web; fi
  if unit_exists telz-whatsapp-gateway; then
    if [[ "$GATEWAY_WAS_ACTIVE" == "active" ]]; then
      systemctl start telz-whatsapp-gateway
    else
      systemctl stop telz-whatsapp-gateway
    fi
  fi
  SERVICES_TOUCHED=false
}

activate_release() {
  local code_dir="$1"
  local temporary="$CURRENT_LINK.telz-rollback-$$"
  [[ ! -e "$temporary" && ! -L "$temporary" ]] || die "link temporario de release ja existe"
  ln -s "$code_dir" "$temporary"
  chown -h root:root "$temporary"
  CURRENT_SWAPPED=true
  mv -Tf -- "$temporary" "$CURRENT_LINK"
}

restore_original_release() {
  local temporary="$CURRENT_LINK.telz-recovery-$$"
  rm -f -- "$CURRENT_LINK.telz-rollback-$$"
  rm -f -- "$temporary"
  ln -s "$ORIGINAL_CODE_DIR" "$temporary"
  chown -h root:root "$temporary"
  mv -Tf -- "$temporary" "$CURRENT_LINK"
  CURRENT_SWAPPED=false
}

run_recovery_step() {
  local label="$1"
  shift
  local recovery_rc
  set +e
  (
    set -Eeuo pipefail
    "$@"
  )
  recovery_rc=$?
  set -e
  if (( recovery_rc != 0 )); then
    echo "[rollback][erro] $label falhou (rc=$recovery_rc)" >&2
    RECOVERY_FAILED=true
  fi
}

on_error() {
  local rc="${1:-1}"
  [[ "$rc" =~ ^[0-9]+$ ]] || rc=1
  ERROR_HANDLER_ARMED=false
  trap - ERR TERM INT HUP
  echo "[rollback][erro] falha durante troca; recuperando release anterior" >&2
  if [[ "$SERVICES_TOUCHED" == "true" || "$CURRENT_SWAPPED" == "true" ]]; then
    run_recovery_step "parada dos servicos para recuperacao" stop_services
  fi
  if [[ "$CURRENT_SWAPPED" == "true" ]]; then
    run_recovery_step "restauracao do symlink current" restore_original_release
  fi
  run_recovery_step "restauracao do estado dos servicos" restore_service_state
  if [[ "$RECOVERY_FAILED" == "false" ]]; then
    run_recovery_step "health da release recuperada" env \
      TELZ_ALEMBIC_TARGET="$DATABASE_REVISION" \
      TELZ_REQUIRE_PUBLIC_HTTPS="$REQUIRE_PUBLIC_HTTPS" \
      TELZ_PUBLIC_HEALTH_URL="$PUBLIC_HEALTH_URL" \
      "$HEALTH_COMMAND" "$INSTALL_DIR"
  fi
  if [[ "$RECOVERY_FAILED" == "true" ]]; then
    run_recovery_step "parada fail-closed dos servicos" stop_services
    echo "[rollback][erro] recuperacao incompleta; intervencao manual obrigatoria" >&2
  fi
  exit "$rc"
}

trap 'rc=$?; on_error "$rc"' ERR
trap 'on_error 143' TERM HUP
trap 'on_error 130' INT
ERROR_HANDLER_ARMED=true

stop_services
activate_release "$TARGET_CODE_DIR"
start_target_services
if unit_exists telz-monitoring; then
  systemctl start telz-monitoring.service
fi

TELZ_ALEMBIC_TARGET="$DATABASE_REVISION" \
  TELZ_REQUIRE_PUBLIC_HTTPS="$REQUIRE_PUBLIC_HTTPS" \
  TELZ_PUBLIC_HEALTH_URL="$PUBLIC_HEALTH_URL" \
  "$HEALTH_COMMAND" "$INSTALL_DIR"

CURRENT_SWAPPED=false
ERROR_HANDLER_ARMED=false
trap - ERR TERM INT HUP
echo "[rollback] concluido release=$TARGET_COMMIT schema_preservado=$DATABASE_REVISION"
