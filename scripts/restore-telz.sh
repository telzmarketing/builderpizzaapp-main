#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

ERROR_HANDLER_ARMED=false

die() {
  echo "[restore][erro] $*" >&2
  if [[ "${ERROR_HANDLER_ARMED:-false}" == "true" ]]; then
    restore_previous_state 1
  fi
  exit 1
}

require_root_owned_executable() {
  local candidate="$1"
  [[ -x "$candidate" && ! -L "$candidate" ]] || die "helper operacional invalido: $candidate"
  [[ "$(stat -c '%U' "$candidate")" == "root" ]] || die "helper deve pertencer a root: $candidate"
  [[ -z "$(find "$candidate" -maxdepth 0 -perm /022 -print -quit)" ]] || \
    die "helper nao pode ser gravavel por grupo/outros: $candidate"
}

SOURCE_SCRIPT="$(realpath -e "$0")"
require_root_owned_executable "$SOURCE_SCRIPT"

[[ "${EUID:-$(id -u)}" -eq 0 ]] || die "execute como root"
[[ $# -eq 2 ]] || die "uso: restore-telz.sh /opt/telz /var/backups/telz/ID"

INSTALL_DIR="$(realpath -e "$1")"
REQUESTED_SET="$2"
SERVICE_USER="${TELZ_SERVICE_USER:-telz}"
BACKUP_DIR="${TELZ_BACKUP_DIR:-/var/backups/telz}"
RELEASES_DIR="${TELZ_RELEASES_DIR:-/var/lib/telz/releases}"
CURRENT_LINK="${TELZ_CURRENT_RELEASE_LINK:-/var/lib/telz/current}"
BACKUP_COMMAND="${TELZ_BACKUP_COMMAND:-/usr/local/bin/backup-telz}"
HEALTH_COMMAND="${TELZ_HEALTH_COMMAND:-/usr/local/sbin/telz-health-check}"
REQUIRE_PUBLIC_HTTPS="${TELZ_REQUIRE_PUBLIC_HTTPS:-true}"
PUBLIC_HEALTH_URL="${TELZ_PUBLIC_HEALTH_URL:-}"
MAINTENANCE_LOCK_DIR="/run/lock/telz"
MAINTENANCE_LOCK="$MAINTENANCE_LOCK_DIR/maintenance.lock"

[[ "$INSTALL_DIR" = /* && "$INSTALL_DIR" != "/" ]] || die "INSTALL_DIR invalido"
[[ "$REQUESTED_SET" = /* ]] || die "o conjunto de backup deve usar caminho absoluto"
[[ -f "$INSTALL_DIR/backend/.env" ]] || die "backend/.env atual nao encontrado"
id "$SERVICE_USER" >/dev/null 2>&1 || die "usuario de servico inexistente: $SERVICE_USER"
[[ -x /usr/bin/python3 ]] || die "/usr/bin/python3 nao encontrado"
[[ "$REQUIRE_PUBLIC_HTTPS" == "true" || "$REQUIRE_PUBLIC_HTTPS" == "false" ]] || \
  die "TELZ_REQUIRE_PUBLIC_HTTPS deve ser true ou false"
[[ "${TELZ_MAINTENANCE_LOCK_HELD:-false}" == "false" ]] || \
  die "restore nao aceita bypass do lock de manutencao"
require_root_owned_executable "$BACKUP_COMMAND"
require_root_owned_executable "$HEALTH_COMMAND"
command -v flock >/dev/null 2>&1 || die "flock nao encontrado"

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

database_identity_fingerprint() {
  /usr/bin/python3 - "$1" <<'PY'
import ast
import hashlib
import json
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

result = None
for raw_line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    line = raw_line.strip()
    if not line or line.startswith("#"):
        continue
    if line.startswith("export "):
        line = line[7:].lstrip()
    key, separator, raw_value = line.partition("=")
    if separator and key.strip() == "DATABASE_URL":
        value = raw_value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            try:
                value = ast.literal_eval(value)
            except (SyntaxError, ValueError):
                raise SystemExit("DATABASE_URL possui quoting invalido")
        result = str(value)
if not result or "\x00" in result or "\n" in result or "\r" in result:
    raise SystemExit("DATABASE_URL ausente ou invalida")
try:
    parsed = urlsplit(result)
    port = parsed.port or 5432
except ValueError:
    raise SystemExit("DATABASE_URL invalida")
scheme = parsed.scheme.split("+", 1)[0]
database = unquote(parsed.path.lstrip("/"))
if scheme not in {"postgres", "postgresql"} or not database:
    raise SystemExit("DATABASE_URL deve apontar para PostgreSQL")
identity = {
    "scheme": "postgresql",
    "host": (parsed.hostname or "localhost").lower().rstrip("."),
    "port": port,
    "database": database,
    "user": unquote(parsed.username or ""),
}
print(hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest())
PY
}

[[ ! -L "$REQUESTED_SET" ]] || die "conjunto de backup nao pode ser symlink"
BACKUP_SET="$(realpath -e "$REQUESTED_SET")"
BACKUP_ROOT="$(realpath -e "$BACKUP_DIR")"
[[ "$BACKUP_SET" == "$BACKUP_ROOT"/* ]] || die "conjunto fora de TELZ_BACKUP_DIR"
[[ ! -L "$BACKUP_ROOT" && ! -L "$BACKUP_SET" ]] || die "arvore de backup contem symlink"
for required_file in manifest.json SHA256SUMS database.dump environment.env; do
  candidate="$BACKUP_SET/$required_file"
  [[ -f "$candidate" && ! -L "$candidate" ]] || die "$required_file ausente ou inseguro"
  [[ "$(stat -c '%U' "$candidate")" == "root" ]] || die "$required_file deve pertencer a root"
  [[ -z "$(find "$candidate" -maxdepth 0 -perm /022 -print -quit)" ]] || \
    die "$required_file gravavel por grupo/outros"
done
for optional_file in uploads.tar.gz baileys.tar.gz; do
  candidate="$BACKUP_SET/$optional_file"
  if [[ -e "$candidate" || -L "$candidate" ]]; then
    [[ -f "$candidate" && ! -L "$candidate" ]] || die "$optional_file inseguro"
  fi
done

[[ ! -L "$INSTALL_DIR/uploads" ]] || die "uploads atual nao pode ser symlink"
[[ ! -L "$INSTALL_DIR/.runtime" ]] || die ".runtime atual nao pode ser symlink"
[[ ! -L "$INSTALL_DIR/.runtime/baileys" ]] || die "runtime Baileys atual nao pode ser symlink"

(cd "$BACKUP_SET" && sha256sum --check --status SHA256SUMS) || die "checksums invalidos"
pg_restore --list "$BACKUP_SET/database.dump" >/dev/null || die "dump PostgreSQL invalido"

validate_archive() {
  local archive="$1"
  local expected_prefix="$2"
  [[ -f "$archive" ]] || return 0
  /usr/bin/python3 - "$archive" "$expected_prefix" <<'PY'
import sys
import tarfile
from pathlib import PurePosixPath

archive, expected_prefix = sys.argv[1], sys.argv[2]
prefix_parts = PurePosixPath(expected_prefix).parts
seen = False
try:
    with tarfile.open(archive, mode="r:gz") as stream:
        for member in stream.getmembers():
            path = PurePosixPath(member.name)
            parts = path.parts
            if path.is_absolute() or not parts or ".." in parts:
                raise SystemExit("archive contem caminho inseguro")
            if tuple(parts[: len(prefix_parts)]) != tuple(prefix_parts):
                raise SystemExit("archive contem entrada fora do prefixo permitido")
            if not (member.isdir() or member.isreg()):
                raise SystemExit("archive contem link, device ou tipo especial")
            seen = True
except (OSError, tarfile.TarError) as exc:
    raise SystemExit("archive tar invalido") from exc
if not seen:
    raise SystemExit("archive tar vazio")
PY
}

validate_archive "$BACKUP_SET/uploads.tar.gz" "uploads"
validate_archive "$BACKUP_SET/baileys.tar.gz" ".runtime/baileys"

readarray -t MANIFEST_VALUES < <(/usr/bin/python3 - "$BACKUP_SET/manifest.json" <<'PY'
import json
import re
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
backup_id = str(data.get("backup_id") or "")
commit = str(data.get("git_commit") or "")
revision = str(data.get("alembic_current") or "")
status = str(data.get("status") or "")
if not re.fullmatch(r"[A-Za-z0-9._-]+", backup_id):
    raise SystemExit("backup_id invalido")
if not re.fullmatch(r"[0-9a-f]{40}", commit):
    raise SystemExit("git_commit invalido")
if not re.fullmatch(r"[A-Za-z0-9_]+", revision):
    raise SystemExit("alembic_current invalido")
if status != "validated":
    raise SystemExit("backup nao validado")
print(backup_id)
print(commit)
print(revision)
PY
)

BACKUP_ID="${MANIFEST_VALUES[0]}"
MANIFEST_COMMIT="${MANIFEST_VALUES[1]}"
MANIFEST_REVISION="${MANIFEST_VALUES[2]}"

validate_release_path() {
  local release_app="$1"
  local releases_real release_real release_root release_id manifest candidate
  [[ -d "$RELEASES_DIR" && ! -L "$RELEASES_DIR" ]] || die "diretorio de releases invalido"
  releases_real="$(realpath -e "$RELEASES_DIR")"
  release_real="$(realpath -e "$release_app")"
  release_root="$(dirname "$release_real")"
  release_id="$(basename "$release_root")"
  [[ "$(dirname "$release_root")" == "$releases_real" && "$(basename "$release_real")" == "app" ]] || \
    die "release ativa fora do layout aprovado"
  [[ "$release_id" =~ ^[0-9a-f]{40}$ ]] || die "identificador da release ativa invalido"
  manifest="$release_real/.telz-release.json"
  for candidate in "$releases_real" "$release_root" "$release_real" "$manifest"; do
    [[ -e "$candidate" && ! -L "$candidate" ]] || die "release ativa possui componente inseguro: $candidate"
    [[ "$(stat -c '%U' "$candidate")" == "root" ]] || die "release ativa deve pertencer a root: $candidate"
    [[ -z "$(find "$candidate" -maxdepth 0 -perm /022 -print -quit)" ]] || \
      die "release ativa gravavel por grupo/outros: $candidate"
  done
  printf '%s\n' "$release_real"
}

ACTIVE_CODE_DIR="$INSTALL_DIR"
ACTIVE_COMMIT=""
ACTIVE_RELEASE_REVISION=""
if [[ -e "$CURRENT_LINK" || -L "$CURRENT_LINK" ]]; then
  [[ -L "$CURRENT_LINK" && "$(stat -c '%U' "$CURRENT_LINK")" == "root" ]] || \
    die "current deve ser symlink pertencente a root"
  ACTIVE_CODE_DIR="$(validate_release_path "$CURRENT_LINK")"
  readarray -t ACTIVE_VALUES < <(/usr/bin/python3 - "$ACTIVE_CODE_DIR/.telz-release.json" "$(basename "$(dirname "$ACTIVE_CODE_DIR")")" "$INSTALL_DIR" <<'PY'
import json
import re
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
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
print(commit)
print(revision)
PY
  )
  [[ "${#ACTIVE_VALUES[@]}" -eq 2 ]] || die "manifest da release ativa invalido"
  ACTIVE_COMMIT="${ACTIVE_VALUES[0]}"
  ACTIVE_RELEASE_REVISION="${ACTIVE_VALUES[1]}"
else
  [[ -d "$INSTALL_DIR/.git" && ! -L "$INSTALL_DIR/.git" ]] || die "repositorio legado nao encontrado"
  ACTIVE_COMMIT="$(sudo -u "$SERVICE_USER" -H git -C "$INSTALL_DIR" rev-parse HEAD)"
fi
[[ "$ACTIVE_COMMIT" =~ ^[0-9a-f]{40}$ ]] || die "commit ativo invalido"
[[ "$MANIFEST_COMMIT" == "$ACTIVE_COMMIT" ]] || \
  die "commit do backup difere da release ativa; ative primeiro a release correspondente"

[[ -x "$ACTIVE_CODE_DIR/.venv/bin/alembic" ]] || die "Alembic ausente na release ativa"
alembic_at_active() {
  sudo -u "$SERVICE_USER" -H env TELZ_PROJECT_ROOT="$INSTALL_DIR" bash -c \
    'cd "$1" && shift && exec .venv/bin/alembic -c backend/alembic.ini "$@"' \
    bash "$ACTIVE_CODE_DIR" "$@"
}
database_revisions_from_active() {
  sudo -u "$SERVICE_USER" -H env TELZ_PROJECT_ROOT="$INSTALL_DIR" \
    "$ACTIVE_CODE_DIR/.venv/bin/python" - "$ACTIVE_CODE_DIR" <<'PY'
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
mapfile -t ACTIVE_HEADS < <(alembic_at_active heads | awk 'NF {print $1}')
[[ "${#ACTIVE_HEADS[@]}" -eq 1 ]] || die "release ativa deve possuir exatamente um head"
[[ -z "$ACTIVE_RELEASE_REVISION" || "${ACTIVE_HEADS[0]}" == "$ACTIVE_RELEASE_REVISION" ]] || \
  die "head da release ativa diverge do manifest"
[[ "${ACTIVE_HEADS[0]}" == "$MANIFEST_REVISION" || \
   "${ACTIVE_HEADS[0]}:$MANIFEST_REVISION" == "20260816_master_completion:20260818_platform_operations" || \
   "${ACTIVE_HEADS[0]}:$MANIFEST_REVISION" == "20260817_platform_wave0:20260818_platform_operations" ]] || \
  die "release ativa nao e compativel com a revision do backup"
mapfile -t PRE_RESTORE_REVISIONS < <(database_revisions_from_active)
[[ "${#PRE_RESTORE_REVISIONS[@]}" -eq 1 ]] || die "banco deve possuir uma revision antes do restore"
PRE_RESTORE_DATABASE_REVISION="${PRE_RESTORE_REVISIONS[0]}"
[[ "${ACTIVE_HEADS[0]}" == "$PRE_RESTORE_DATABASE_REVISION" || \
   "${ACTIVE_HEADS[0]}:$PRE_RESTORE_DATABASE_REVISION" == "20260816_master_completion:20260818_platform_operations" || \
   "${ACTIVE_HEADS[0]}:$PRE_RESTORE_DATABASE_REVISION" == "20260817_platform_wave0:20260818_platform_operations" ]] || \
  die "release ativa nao e compativel com o banco atual"

CURRENT_DATABASE_IDENTITY="$(database_identity_fingerprint "$INSTALL_DIR/backend/.env")"
BACKUP_DATABASE_IDENTITY="$(database_identity_fingerprint "$BACKUP_SET/environment.env")"
[[ "$BACKUP_DATABASE_IDENTITY" == "$CURRENT_DATABASE_IDENTITY" ]] || \
  die "identidade canonica do banco do backup difere do destino"

EXPECTED_CONFIRMATION="RESTAURAR $BACKUP_ID"
ANSWER="${TELZ_RESTORE_CONFIRM:-}"
if [[ -z "$ANSWER" ]]; then
  echo "[restore] operacao destrutiva protegida por safety backup."
  read -r -p "Digite '$EXPECTED_CONFIRMATION' para continuar: " ANSWER
fi
[[ "$ANSWER" == "$EXPECTED_CONFIRMATION" ]] || die "confirmacao invalida"

CONNECTION_DIR="$(mktemp -d /tmp/telz-restore-libpq.XXXXXX)"
chmod 0700 "$CONNECTION_DIR"
prepare_libpq() {
  /usr/bin/python3 - "$1" "$2" <<'PY'
import ast
import os
import sys
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit, urlunsplit

database_url = None
for raw_line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    line = raw_line.strip()
    if not line or line.startswith("#"):
        continue
    if line.startswith("export "):
        line = line[7:].lstrip()
    key, separator, raw_value = line.partition("=")
    if separator and key.strip() == "DATABASE_URL":
        value = raw_value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            try:
                value = ast.literal_eval(value)
            except (SyntaxError, ValueError):
                raise SystemExit("DATABASE_URL possui quoting invalido")
        database_url = str(value)
if not database_url or any(char in database_url for char in ("\x00", "\n", "\r")):
    raise SystemExit("DATABASE_URL ausente ou invalida")
parsed = urlsplit(database_url)
scheme = parsed.scheme.split("+", 1)[0]
if scheme not in {"postgresql", "postgres"} or not parsed.path:
    raise SystemExit("DATABASE_URL deve apontar para PostgreSQL")
try:
    port = parsed.port
except ValueError as exc:
    raise SystemExit("porta PostgreSQL invalida") from exc
username = unquote(parsed.username or "")
password = unquote(parsed.password or "") if parsed.password is not None else ""
if any(char in password for char in ("\x00", "\n", "\r")):
    raise SystemExit("senha PostgreSQL invalida")
host = parsed.hostname or ""
host_part = f"[{host}]" if ":" in host and not host.startswith("[") else host
user_part = quote(username, safe="") if username else ""
netloc = f"{user_part}@" if user_part else ""
netloc += host_part
if port is not None:
    netloc += f":{port}"
safe_uri = urlunsplit((scheme, netloc, parsed.path, parsed.query, ""))
target = Path(sys.argv[2])
(target / "pgdatabase").write_text(safe_uri, encoding="utf-8")
escaped = password.replace("\\", "\\\\").replace(":", "\\:")
(target / "pgpass").write_text(
    f"*:*:*:*:{escaped}\n" if parsed.password is not None else "",
    encoding="utf-8",
)
os.chmod(target / "pgdatabase", 0o600)
os.chmod(target / "pgpass", 0o600)
PY
}
prepare_libpq "$INSTALL_DIR/backend/.env" "$CONNECTION_DIR"
PGDATABASE_SAFE="$(<"$CONNECTION_DIR/pgdatabase")"

RESULT_FILE="$(mktemp /tmp/telz-safety-backup.XXXXXX)"
chmod 0600 "$RESULT_FILE"
STAGE_DIR=""
SAFETY_SET=""
SAFETY_REVISION=""
cleanup_restore_stage() {
  if [[ -n "${RESULT_FILE:-}" && "$RESULT_FILE" == /tmp/telz-safety-backup.* ]]; then
    rm -f -- "$RESULT_FILE"
  fi
  if [[ -n "${STAGE_DIR:-}" && "$STAGE_DIR" == /var/lib/telz/restore-stage-* && -d "$STAGE_DIR" && ! -L "$STAGE_DIR" ]]; then
    rm -rf -- "$STAGE_DIR"
  fi
  if [[ -n "${CONNECTION_DIR:-}" && "$CONNECTION_DIR" == /tmp/telz-restore-libpq.* && -d "$CONNECTION_DIR" && ! -L "$CONNECTION_DIR" ]]; then
    rm -rf -- "$CONNECTION_DIR"
  fi
}
trap cleanup_restore_stage EXIT

RESTORE_ID="$(date -u +%Y%m%d-%H%M%S)-$$"
install -d -m 0755 -o root -g root /var/lib/telz
STAGE_DIR="$(mktemp -d "/var/lib/telz/restore-stage-$RESTORE_ID.XXXXXX")"
ROLLBACK_DIR="/var/lib/telz/restore-rollback-$RESTORE_ID"
install -d -m 0700 -o root -g root "$ROLLBACK_DIR"

if [[ -f "$BACKUP_SET/uploads.tar.gz" ]]; then
  tar --no-same-owner --no-same-permissions -C "$STAGE_DIR" -xzf "$BACKUP_SET/uploads.tar.gz"
fi
if [[ -f "$BACKUP_SET/baileys.tar.gz" ]]; then
  tar --no-same-owner --no-same-permissions -C "$STAGE_DIR" -xzf "$BACKUP_SET/baileys.tar.gz"
fi
[[ ! -L "$STAGE_DIR/uploads" ]] || die "archive de uploads produziu symlink invalido"
[[ ! -L "$STAGE_DIR/.runtime/baileys" ]] || die "archive Baileys produziu symlink invalido"

normalize_staged_tree() {
  local tree="$1"
  [[ -d "$tree" && ! -L "$tree" ]] || return 0
  [[ -z "$(find "$tree" -xdev -type l -print -quit)" ]] || die "staging contem symlink"
  [[ -z "$(find "$tree" -xdev ! -type d ! -type f -print -quit)" ]] || die "staging contem tipo especial"
  chown -hR "$SERVICE_USER:$SERVICE_USER" "$tree"
  find "$tree" -xdev -type d -exec chmod 0700 {} +
  find "$tree" -xdev -type f -exec chmod 0600 {} +
  [[ -z "$(find "$tree" -xdev -type l -print -quit)" ]] || die "staging mudou para symlink"
  [[ -z "$(find "$tree" -xdev ! -type d ! -type f -print -quit)" ]] || die "staging mudou para tipo especial"
  [[ -z "$(find "$tree" -xdev \( ! -user "$SERVICE_USER" -o ! -group "$SERVICE_USER" \) -print -quit)" ]] || \
    die "ownership do staging invalido"
}
normalize_staged_tree "$STAGE_DIR/uploads"
normalize_staged_tree "$STAGE_DIR/.runtime/baileys"

DB_MODIFIED=false
UPLOADS_OLD_MOVED=false
UPLOADS_NEW_INSTALLED=false
BAILEYS_OLD_MOVED=false
BAILEYS_NEW_INSTALLED=false
SERVICES_STOPPED=false
RECOVERY_FAILED=false

unit_exists() {
  systemctl list-unit-files "$1.service" --no-legend 2>/dev/null | grep -q "^$1.service"
}

stop_services() {
  if unit_exists telz-whatsapp-gateway; then
    systemctl stop telz-whatsapp-gateway
  fi
  systemctl stop telz-api telz-web
  SERVICES_STOPPED=true
}

start_services() {
  systemctl start telz-api telz-web
  if unit_exists telz-whatsapp-gateway; then
    systemctl start telz-whatsapp-gateway
  fi
  SERVICES_STOPPED=false
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
    echo "[restore][erro] $label falhou (rc=$recovery_rc)" >&2
    RECOVERY_FAILED=true
  fi
}

restore_safety_database() {
  PGPASSFILE="$CONNECTION_DIR/pgpass" PGDATABASE="$PGDATABASE_SAFE" \
    pg_restore --clean --if-exists --no-owner --exit-on-error --single-transaction \
      < "$SAFETY_SET/database.dump"
}

remove_failed_uploads() {
  [[ -d "$INSTALL_DIR/uploads" && ! -L "$INSTALL_DIR/uploads" ]] || return 1
  mv -- "$INSTALL_DIR/uploads" "$ROLLBACK_DIR/failed-uploads"
}

restore_old_uploads() {
  [[ -d "$ROLLBACK_DIR/uploads" && ! -L "$ROLLBACK_DIR/uploads" ]] || return 1
  mv -- "$ROLLBACK_DIR/uploads" "$INSTALL_DIR/uploads"
}

remove_failed_baileys() {
  [[ -d "$INSTALL_DIR/.runtime/baileys" && ! -L "$INSTALL_DIR/.runtime/baileys" ]] || return 1
  mv -- "$INSTALL_DIR/.runtime/baileys" "$ROLLBACK_DIR/failed-baileys"
}

restore_old_baileys() {
  [[ -d "$ROLLBACK_DIR/baileys" && ! -L "$ROLLBACK_DIR/baileys" ]] || return 1
  install -d -m 0700 -o "$SERVICE_USER" -g "$SERVICE_USER" "$INSTALL_DIR/.runtime"
  mv -- "$ROLLBACK_DIR/baileys" "$INSTALL_DIR/.runtime/baileys"
}

validate_persistent_ownership() {
  local tree
  for tree in "$INSTALL_DIR/uploads" "$INSTALL_DIR/.runtime/baileys"; do
    [[ ! -e "$tree" ]] && continue
    [[ -d "$tree" && ! -L "$tree" ]] || return 1
    [[ -z "$(find "$tree" -xdev -type l -print -quit)" ]] || return 1
    [[ -z "$(find "$tree" -xdev ! -type d ! -type f -print -quit)" ]] || return 1
    [[ -z "$(find "$tree" -xdev \( ! -user "$SERVICE_USER" -o ! -group "$SERVICE_USER" \) -print -quit)" ]] || return 1
  done
}

validate_database_revision() {
  local expected_revision="$1"
  local -a actual_revisions
  mapfile -t actual_revisions < <(database_revisions_from_active)
  [[ "${#actual_revisions[@]}" -eq 1 && "${actual_revisions[0]}" == "$expected_revision" ]]
}

restore_previous_state() {
  local original_rc="${1:-1}"
  [[ "$original_rc" =~ ^[0-9]+$ ]] || original_rc=1
  ERROR_HANDLER_ARMED=false
  trap - ERR TERM INT HUP
  echo "[restore][erro] restauracao falhou; iniciando rollback pelo safety backup" >&2
  run_recovery_step "parada dos servicos" stop_services

  if [[ "$DB_MODIFIED" == "true" && -f "$SAFETY_SET/database.dump" ]]; then
    run_recovery_step "restauracao do safety dump" restore_safety_database
  fi

  if [[ "$UPLOADS_NEW_INSTALLED" == "true" && -e "$INSTALL_DIR/uploads" ]]; then
    run_recovery_step "remocao dos uploads restaurados" remove_failed_uploads
  fi
  if [[ "$UPLOADS_OLD_MOVED" == "true" ]]; then
    run_recovery_step "retorno dos uploads anteriores" restore_old_uploads
  fi
  if [[ "$BAILEYS_NEW_INSTALLED" == "true" && -e "$INSTALL_DIR/.runtime/baileys" ]]; then
    run_recovery_step "remocao do Baileys restaurado" remove_failed_baileys
  fi
  if [[ "$BAILEYS_OLD_MOVED" == "true" ]]; then
    run_recovery_step "retorno do Baileys anterior" restore_old_baileys
  fi

  run_recovery_step "revision restaurada do safety backup" validate_database_revision \
    "${SAFETY_REVISION:-$PRE_RESTORE_DATABASE_REVISION}"
  run_recovery_step "ownership dos dados persistentes" validate_persistent_ownership
  if [[ "$RECOVERY_FAILED" == "false" ]]; then
    run_recovery_step "reinicio dos servicos" start_services
  fi
  if [[ "$RECOVERY_FAILED" == "false" ]]; then
    run_recovery_step "health do safety backup" env \
      TELZ_ALEMBIC_TARGET="${SAFETY_REVISION:-$PRE_RESTORE_DATABASE_REVISION}" \
      TELZ_REQUIRE_PUBLIC_HTTPS="$REQUIRE_PUBLIC_HTTPS" \
      TELZ_PUBLIC_HEALTH_URL="$PUBLIC_HEALTH_URL" \
      "$HEALTH_COMMAND" "$INSTALL_DIR"
  fi
  if [[ "$RECOVERY_FAILED" == "true" ]]; then
    run_recovery_step "parada fail-closed dos servicos" stop_services
    echo "[restore][erro] recuperacao incompleta; servicos permanecem parados" >&2
  fi
  echo "[restore][erro] safety backup preservado em $SAFETY_SET" >&2
  exit "$original_rc"
}
trap 'rc=$?; restore_previous_state "$rc"' ERR
trap 'restore_previous_state 143' TERM HUP
trap 'restore_previous_state 130' INT
ERROR_HANDLER_ARMED=true

stop_services

echo "[restore] criando safety backup coerente com os servicos parados"
TELZ_MAINTENANCE_LOCK_HELD=true \
  TELZ_BACKUP_RESULT_FILE="$RESULT_FILE" TELZ_SERVICE_USER="$SERVICE_USER" \
  "$BACKUP_COMMAND" "$INSTALL_DIR"
SAFETY_SET="$(<"$RESULT_FILE")"
[[ -d "$SAFETY_SET" && "$SAFETY_SET" == "$BACKUP_ROOT"/* ]] || die "safety backup invalido"
SAFETY_REVISION="$(/usr/bin/python3 - "$SAFETY_SET/manifest.json" <<'PY'
import json
import re
import sys
from pathlib import Path

try:
    revision = str(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")).get("alembic_current") or "")
except Exception:
    raise SystemExit("manifest do safety backup invalido")
if not re.fullmatch(r"[A-Za-z0-9_]+", revision):
    raise SystemExit("revision do safety backup invalida")
print(revision)
PY
)"
[[ "$SAFETY_REVISION" == "$PRE_RESTORE_DATABASE_REVISION" ]] || die "safety backup diverge do banco quiescido"

echo "[restore] restaurando PostgreSQL revision=$MANIFEST_REVISION"
DB_MODIFIED=true
PGPASSFILE="$CONNECTION_DIR/pgpass" PGDATABASE="$PGDATABASE_SAFE" \
  pg_restore --clean --if-exists --no-owner --exit-on-error --single-transaction \
    < "$BACKUP_SET/database.dump"
validate_database_revision "$MANIFEST_REVISION" || die "dump restaurado diverge da revision do manifest"

[[ ! -L "$INSTALL_DIR/uploads" ]] || die "uploads atual nao pode ser symlink"
[[ ! -L "$INSTALL_DIR/.runtime" ]] || die "runtime atual nao pode ser symlink"
[[ ! -L "$INSTALL_DIR/.runtime/baileys" ]] || die "runtime Baileys atual nao pode ser symlink"

if [[ -d "$INSTALL_DIR/uploads" ]]; then
  UPLOADS_OLD_MOVED=true
  mv -- "$INSTALL_DIR/uploads" "$ROLLBACK_DIR/uploads"
fi
if [[ -d "$STAGE_DIR/uploads" ]]; then
  UPLOADS_NEW_INSTALLED=true
  mv -- "$STAGE_DIR/uploads" "$INSTALL_DIR/uploads"
fi

if [[ -d "$INSTALL_DIR/.runtime/baileys" ]]; then
  BAILEYS_OLD_MOVED=true
  mv -- "$INSTALL_DIR/.runtime/baileys" "$ROLLBACK_DIR/baileys"
fi
if [[ -d "$STAGE_DIR/.runtime/baileys" ]]; then
  install -d -m 0700 -o "$SERVICE_USER" -g "$SERVICE_USER" "$INSTALL_DIR/.runtime"
  BAILEYS_NEW_INSTALLED=true
  mv -- "$STAGE_DIR/.runtime/baileys" "$INSTALL_DIR/.runtime/baileys"
fi

validate_persistent_ownership || die "dados restaurados falharam na revalidacao final"

start_services
TELZ_ALEMBIC_TARGET="$MANIFEST_REVISION" \
  TELZ_REQUIRE_PUBLIC_HTTPS="$REQUIRE_PUBLIC_HTTPS" \
  TELZ_PUBLIC_HEALTH_URL="$PUBLIC_HEALTH_URL" \
  "$HEALTH_COMMAND" "$INSTALL_DIR"

ERROR_HANDLER_ARMED=false
trap - ERR TERM INT HUP
rm -rf -- "$STAGE_DIR"
STAGE_DIR=""
rm -f -- "$RESULT_FILE"
RESULT_FILE=""
rm -rf -- "$CONNECTION_DIR"
CONNECTION_DIR=""
trap - EXIT

echo "[restore] concluido backup_id=$BACKUP_ID"
echo "[restore] safety backup preservado em $SAFETY_SET"
echo "[restore] estado anterior de arquivos preservado em $ROLLBACK_DIR"
