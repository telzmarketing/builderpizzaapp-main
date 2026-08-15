#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

ERROR_HANDLER_ARMED=false

die() {
  echo "[backup][erro] $*" >&2
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

INSTALL_INPUT="${1:-/opt/telz}"
[[ "$INSTALL_INPUT" = /* && "$INSTALL_INPUT" != "/" && ! -L "$INSTALL_INPUT" ]] || \
  die "INSTALL_DIR absoluto, real e especifico e obrigatorio"
INSTALL_DIR="$(realpath -e "$INSTALL_INPUT")"
BACKUP_DIR="${TELZ_BACKUP_DIR:-/var/backups/telz}"
SERVICE_USER="${TELZ_SERVICE_USER:-telz}"
RESULT_FILE="${TELZ_BACKUP_RESULT_FILE:-}"
HEALTH_COMMAND="${TELZ_HEALTH_COMMAND:-/usr/local/sbin/telz-health-check}"
RELEASES_DIR="${TELZ_RELEASES_DIR:-/var/lib/telz/releases}"
CURRENT_LINK="${TELZ_CURRENT_RELEASE_LINK:-/var/lib/telz/current}"
MAINTENANCE_LOCK_DIR="/run/lock/telz"
MAINTENANCE_LOCK="$MAINTENANCE_LOCK_DIR/maintenance.lock"

[[ "$BACKUP_DIR" = /* && "$BACKUP_DIR" != "/" && "$BACKUP_DIR" != "$INSTALL_DIR" && ! -L "$BACKUP_DIR" ]] || \
  die "TELZ_BACKUP_DIR invalido"
[[ "$RELEASES_DIR" = /* && "$RELEASES_DIR" != "/" ]] || die "TELZ_RELEASES_DIR invalido"
[[ "$CURRENT_LINK" = /* ]] || die "TELZ_CURRENT_RELEASE_LINK invalido"
[[ -d "$INSTALL_DIR/backend" && ! -L "$INSTALL_DIR/backend" ]] || die "backend invalido em $INSTALL_DIR"
[[ -f "$INSTALL_DIR/backend/.env" && ! -L "$INSTALL_DIR/backend/.env" ]] || \
  die "backend/.env nao encontrado ou inseguro em $INSTALL_DIR"
id "$SERVICE_USER" >/dev/null 2>&1 || die "usuario de servico inexistente: $SERVICE_USER"
command -v pg_dump >/dev/null 2>&1 || die "pg_dump nao encontrado"
command -v pg_restore >/dev/null 2>&1 || die "pg_restore nao encontrado"
command -v sha256sum >/dev/null 2>&1 || die "sha256sum nao encontrado"
command -v flock >/dev/null 2>&1 || die "flock nao encontrado"
[[ -x /usr/bin/python3 ]] || die "/usr/bin/python3 nao encontrado"

acquire_maintenance_lock() {
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
  case "${TELZ_MAINTENANCE_LOCK_HELD:-false}" in
    true)
      [[ -e "/proc/$$/fd/9" ]] || die "bypass do lock requer fd 9 herdado"
      [[ "$(readlink -f "/proc/$$/fd/9")" == "$MAINTENANCE_LOCK" ]] || \
        die "fd 9 nao aponta para o lock de manutencao"
      [[ "$(stat -Lc '%d:%i' "/proc/$$/fd/9")" == "$(stat -c '%d:%i' "$MAINTENANCE_LOCK")" ]] || \
        die "fd 9 nao corresponde ao inode do lock"
      exec 8<>"$MAINTENANCE_LOCK"
      if flock -n 8; then
        flock -u 8
        exec 8>&-
        die "fd 9 herdado nao possuia lock preexistente"
      fi
      exec 8>&-
      flock -n 9 || die "lock herdado nao esta disponivel"
      ;;
    false|"")
      exec 9<>"$MAINTENANCE_LOCK"
      flock -n 9 || die "outra manutencao Telz esta em execucao"
      ;;
    *) die "TELZ_MAINTENANCE_LOCK_HELD deve ser true ou false" ;;
  esac
}
acquire_maintenance_lock

reject_persistent_tree() {
  local path="$1"
  [[ ! -L "$path" ]] || die "caminho persistente nao pode ser symlink: $path"
  if [[ -e "$path" ]]; then
    [[ -d "$path" ]] || die "caminho persistente deve ser diretorio: $path"
    [[ -z "$(find "$path" -xdev -type l -print -quit)" ]] || die "caminho persistente contem symlink: $path"
    [[ -z "$(find "$path" -xdev ! -type d ! -type f -print -quit)" ]] || \
      die "caminho persistente contem tipo especial: $path"
  fi
}

[[ ! -L "$INSTALL_DIR/.runtime" ]] || die "INSTALL_DIR/.runtime nao pode ser symlink"
reject_persistent_tree "$INSTALL_DIR/uploads"
if [[ -e "$INSTALL_DIR/.runtime" ]]; then
  [[ -d "$INSTALL_DIR/.runtime" ]] || die "INSTALL_DIR/.runtime deve ser diretorio"
  reject_persistent_tree "$INSTALL_DIR/.runtime/baileys"
fi

validate_archive() {
  local archive="$1"
  local expected_prefix="$2"
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

validate_release_path() {
  local release_app="$1"
  local releases_real release_real release_root manifest candidate
  [[ -d "$RELEASES_DIR" && ! -L "$RELEASES_DIR" ]] || die "diretorio de releases invalido"
  releases_real="$(realpath -e "$RELEASES_DIR")"
  release_real="$(realpath -e "$release_app")"
  [[ "$release_real" =~ ^${releases_real}/[0-9a-f]{40}/app$ ]] || die "release ativa fora do layout aprovado"
  release_root="$(dirname "$release_real")"
  manifest="$release_real/.telz-release.json"
  for candidate in "$releases_real" "$release_root" "$release_real" "$manifest"; do
    [[ -e "$candidate" && ! -L "$candidate" ]] || die "release ativa possui componente inseguro: $candidate"
    [[ "$(stat -c '%U' "$candidate")" == "root" ]] || die "release ativa deve pertencer a root: $candidate"
    [[ -z "$(find "$candidate" -maxdepth 0 -perm /022 -print -quit)" ]] || \
      die "release ativa gravavel por grupo/outros: $candidate"
  done
  [[ -f "$manifest" ]] || die "manifest da release ativa ausente"
  printf '%s\n' "$release_real"
}

ACTIVE_CODE_DIR="$INSTALL_DIR"
ACTIVE_RELEASE_COMMIT=""
ACTIVE_RELEASE_REVISION=""
if [[ -e "$CURRENT_LINK" || -L "$CURRENT_LINK" ]]; then
  [[ -L "$CURRENT_LINK" && "$(stat -c '%U' "$CURRENT_LINK")" == "root" ]] || \
    die "current deve ser symlink pertencente a root"
  ACTIVE_CODE_DIR="$(validate_release_path "$CURRENT_LINK")"
  readarray -t RELEASE_VALUES < <(/usr/bin/python3 - "$ACTIVE_CODE_DIR/.telz-release.json" "$(basename "$(dirname "$ACTIVE_CODE_DIR")")" "$INSTALL_DIR" <<'PY'
import json
import re
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
commit = str(data.get("git_commit") or "")
revision = str(data.get("alembic_revision") or "")
if data.get("schema_version") != 2 or data.get("status") != "validated":
    raise SystemExit("manifest da release nao validado")
if not re.fullmatch(r"[0-9a-f]{40}", commit) or commit != sys.argv[2]:
    raise SystemExit("commit do manifest da release invalido")
if not re.fullmatch(r"[A-Za-z0-9_]+", revision):
    raise SystemExit("revision do manifest da release invalida")
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
  [[ "${#RELEASE_VALUES[@]}" -eq 2 ]] || die "manifest da release ativa invalido"
  ACTIVE_RELEASE_COMMIT="${RELEASE_VALUES[0]}"
  ACTIVE_RELEASE_REVISION="${RELEASE_VALUES[1]}"
else
  [[ -d "$INSTALL_DIR/.git" && ! -L "$INSTALL_DIR/.git" ]] || die "repositorio legado nao encontrado"
  ACTIVE_RELEASE_COMMIT="$(sudo -u "$SERVICE_USER" -H git -C "$INSTALL_DIR" rev-parse HEAD 2>/dev/null)"
  [[ "$ACTIVE_RELEASE_COMMIT" =~ ^[0-9a-f]{40}$ ]] || die "commit legado ativo invalido"
fi

[[ -x "$ACTIVE_CODE_DIR/.venv/bin/alembic" ]] || die "Alembic ausente na release ativa"
alembic_from_active() {
  sudo -u "$SERVICE_USER" -H env TELZ_PROJECT_ROOT="$INSTALL_DIR" \
    bash -c 'cd "$1" && shift && exec .venv/bin/alembic -c backend/alembic.ini "$@"' \
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
mapfile -t CODE_HEADS < <(alembic_from_active heads | awk 'NF {print $1}')
mapfile -t DB_CURRENTS < <(database_revisions_from_active)
[[ "${#CODE_HEADS[@]}" -eq 1 && "${CODE_HEADS[0]}" =~ ^[A-Za-z0-9_]+$ ]] || \
  die "release ativa deve possuir exatamente um head Alembic conhecido"
[[ "${#DB_CURRENTS[@]}" -eq 1 && "${DB_CURRENTS[0]}" =~ ^[A-Za-z0-9_]+$ ]] || \
  die "banco deve possuir exatamente uma revision Alembic conhecida"
CODE_HEAD="${CODE_HEADS[0]}"
DB_CURRENT="${DB_CURRENTS[0]}"
[[ -z "$ACTIVE_RELEASE_REVISION" || "$CODE_HEAD" == "$ACTIVE_RELEASE_REVISION" ]] || \
  die "head da release ativa diverge do manifest"

schema_pair_is_compatible() {
  [[ "$1" == "$2" ]] || \
    [[ "$1:$2" == "20260816_master_completion:20260818_platform_operations" ]] || \
    [[ "$1:$2" == "20260817_platform_wave0:20260818_platform_operations" ]]
}
schema_pair_is_compatible "$CODE_HEAD" "$DB_CURRENT" || \
  die "release ativa ($CODE_HEAD) nao e compativel com o banco ($DB_CURRENT)"

OVERRIDE_COMMIT="${TELZ_BACKUP_GIT_COMMIT_OVERRIDE:-}"
OVERRIDE_REVISION="${TELZ_BACKUP_ALEMBIC_REVISION_OVERRIDE:-}"
if [[ -n "$OVERRIDE_COMMIT" || -n "$OVERRIDE_REVISION" ]]; then
  [[ "$OVERRIDE_COMMIT" =~ ^[0-9a-f]{40}$ ]] || die "override de commit invalido"
  [[ "$OVERRIDE_REVISION" =~ ^[A-Za-z0-9_]+$ ]] || die "override de revision invalido"
  [[ "$OVERRIDE_COMMIT" == "$ACTIVE_RELEASE_COMMIT" ]] || die "override de commit difere da release ativa"
  [[ "$OVERRIDE_REVISION" == "$DB_CURRENT" ]] || die "override de revision difere do banco ativo"
  GIT_COMMIT="$OVERRIDE_COMMIT"
  ALEMBIC_CURRENT="$OVERRIDE_REVISION"
else
  GIT_COMMIT="$ACTIVE_RELEASE_COMMIT"
  ALEMBIC_CURRENT="$DB_CURRENT"
fi

unit_exists() {
  systemctl list-unit-files "$1.service" --no-legend 2>/dev/null | grep -q "^$1.service"
}

API_WAS_ACTIVE="$(systemctl is-active telz-api 2>/dev/null || true)"
WEB_WAS_ACTIVE="$(systemctl is-active telz-web 2>/dev/null || true)"
GATEWAY_WAS_ACTIVE="inactive"
if unit_exists telz-whatsapp-gateway; then
  GATEWAY_WAS_ACTIVE="$(systemctl is-active telz-whatsapp-gateway 2>/dev/null || true)"
fi
if [[ "$API_WAS_ACTIVE" == "active" || "$WEB_WAS_ACTIVE" == "active" ]]; then
  require_root_owned_executable "$HEALTH_COMMAND"
fi

SERVICES_QUIESCED=false
RECOVERY_FAILED=false

stop_writers() {
  SERVICES_QUIESCED=true
  if unit_exists telz-whatsapp-gateway; then systemctl stop telz-whatsapp-gateway; fi
  systemctl stop telz-api telz-web
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
}

validate_recovered_services() {
  if [[ "$API_WAS_ACTIVE" == "active" && "$WEB_WAS_ACTIVE" == "active" ]]; then
    TELZ_ALEMBIC_TARGET="$ALEMBIC_CURRENT" TELZ_REQUIRE_PUBLIC_HTTPS=false \
      "$HEALTH_COMMAND" "$INSTALL_DIR"
  fi
}

run_recovery_step() {
  local label="$1"
  shift
  local recovery_rc
  set +e
  (set -Eeuo pipefail; "$@")
  recovery_rc=$?
  set -e
  if (( recovery_rc != 0 )); then
    echo "[backup][erro] $label falhou (rc=$recovery_rc)" >&2
    RECOVERY_FAILED=true
  fi
}

on_error() {
  local rc="${1:-1}"
  [[ "$rc" =~ ^[0-9]+$ ]] || rc=1
  ERROR_HANDLER_ARMED=false
  trap - ERR TERM INT HUP
  if [[ "$SERVICES_QUIESCED" == "true" ]]; then
    run_recovery_step "restauracao dos estados dos servicos" restore_service_state
    if [[ "$RECOVERY_FAILED" == "false" ]]; then
      run_recovery_step "health local apos falha do backup" validate_recovered_services
    fi
  fi
  if [[ "$RECOVERY_FAILED" == "true" ]]; then
    run_recovery_step "parada fail-closed dos writers" stop_writers
    echo "[backup][erro] recuperacao incompleta; writers permanecem parados" >&2
  fi
  exit "$rc"
}

trap 'rc=$?; on_error "$rc"' ERR
trap 'on_error 143' TERM HUP
trap 'on_error 130' INT
ERROR_HANDLER_ARMED=true

echo "[backup] quiescendo writers para snapshot consistente"
stop_writers

install -d -m 0700 -o root -g root "$BACKUP_DIR"

CREATED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
BACKUP_ID="$(date -u +%Y%m%d-%H%M%S)-$$"
TEMP_DIR="$BACKUP_DIR/.tmp-$BACKUP_ID"
FINAL_DIR="$BACKUP_DIR/$BACKUP_ID"

[[ ! -e "$TEMP_DIR" && ! -e "$FINAL_DIR" ]] || die "identificador de backup ja existe"
mkdir -m 0700 "$TEMP_DIR"

cleanup() {
  if [[ -n "${TEMP_DIR:-}" && "$TEMP_DIR" == "$BACKUP_DIR"/.tmp-* && -d "$TEMP_DIR" && ! -L "$TEMP_DIR" ]]; then
    rm -rf -- "$TEMP_DIR"
  fi
}
trap cleanup EXIT

prepare_libpq() {
  local env_file="$1"
  local output_dir="$2"
  /usr/bin/python3 - "$env_file" "$output_dir" <<'PY'
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

prepare_libpq "$INSTALL_DIR/backend/.env" "$TEMP_DIR"
PGDATABASE_SAFE="$(<"$TEMP_DIR/pgdatabase")"
echo "[backup] criando dump PostgreSQL"
PGPASSFILE="$TEMP_DIR/pgpass" PGDATABASE="$PGDATABASE_SAFE" \
  pg_dump --format=custom > "$TEMP_DIR/database.dump"
rm -f -- "$TEMP_DIR/pgdatabase" "$TEMP_DIR/pgpass"
[[ -s "$TEMP_DIR/database.dump" ]] || die "dump PostgreSQL vazio"
pg_restore --list "$TEMP_DIR/database.dump" >/dev/null

if [[ -d "$INSTALL_DIR/uploads" ]]; then
  tar -C "$INSTALL_DIR" -czf "$TEMP_DIR/uploads.tar.gz" uploads
  [[ -s "$TEMP_DIR/uploads.tar.gz" ]] || die "arquivo de uploads vazio"
  validate_archive "$TEMP_DIR/uploads.tar.gz" "uploads"
fi

if [[ -d "$INSTALL_DIR/.runtime/baileys" ]]; then
  tar -C "$INSTALL_DIR" -czf "$TEMP_DIR/baileys.tar.gz" .runtime/baileys
  [[ -s "$TEMP_DIR/baileys.tar.gz" ]] || die "arquivo Baileys vazio"
  validate_archive "$TEMP_DIR/baileys.tar.gz" ".runtime/baileys"
fi

install -m 0600 -o root -g root "$INSTALL_DIR/backend/.env" "$TEMP_DIR/environment.env"
cmp -s "$INSTALL_DIR/backend/.env" "$TEMP_DIR/environment.env" || die "copia do ambiente divergiu"

COMPONENTS=(database.dump environment.env)
[[ -f "$TEMP_DIR/uploads.tar.gz" ]] && COMPONENTS+=(uploads.tar.gz)
[[ -f "$TEMP_DIR/baileys.tar.gz" ]] && COMPONENTS+=(baileys.tar.gz)

: > "$TEMP_DIR/SHA256SUMS"
for component in "${COMPONENTS[@]}"; do
  (cd "$TEMP_DIR" && sha256sum "$component") >> "$TEMP_DIR/SHA256SUMS"
done
(cd "$TEMP_DIR" && sha256sum --check --status SHA256SUMS) || die "validacao de checksums falhou"

export TELZ_MANIFEST_BACKUP_ID="$BACKUP_ID"
export TELZ_MANIFEST_CREATED_AT="$CREATED_AT"
export TELZ_MANIFEST_GIT_COMMIT="$GIT_COMMIT"
export TELZ_MANIFEST_ALEMBIC_CURRENT="$ALEMBIC_CURRENT"
export TELZ_MANIFEST_DIR="$TEMP_DIR"

/usr/bin/python3 - <<'PY'
import hashlib
import json
import os
from pathlib import Path

root = Path(os.environ["TELZ_MANIFEST_DIR"])
names = ("database.dump", "environment.env", "uploads.tar.gz", "baileys.tar.gz")
components = {}
for name in names:
    path = root / name
    if not path.is_file():
        continue
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    components[name] = {
        "size_bytes": path.stat().st_size,
        "sha256": digest.hexdigest(),
    }

manifest = {
    "schema_version": 1,
    "backup_id": os.environ["TELZ_MANIFEST_BACKUP_ID"],
    "created_at": os.environ["TELZ_MANIFEST_CREATED_AT"],
    "git_commit": os.environ["TELZ_MANIFEST_GIT_COMMIT"],
    "alembic_current": os.environ["TELZ_MANIFEST_ALEMBIC_CURRENT"],
    "status": "validated",
    "consistency": "quiesced_snapshot",
    "components": components,
}
target = root / "manifest.json"
temporary = root / ".manifest.json.tmp"
temporary.write_text(json.dumps(manifest, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
os.replace(temporary, target)
PY

chmod 0600 "$TEMP_DIR"/*
chown -R root:root "$TEMP_DIR"
mv -- "$TEMP_DIR" "$FINAL_DIR"
TEMP_DIR=""

LATEST_TMP="$BACKUP_DIR/.latest-$BACKUP_ID"
ln -s "$BACKUP_ID" "$LATEST_TMP"
mv -Tf -- "$LATEST_TMP" "$BACKUP_DIR/latest"

if [[ -n "$RESULT_FILE" ]]; then
  [[ "$RESULT_FILE" = /* && ! -L "$RESULT_FILE" ]] || die "TELZ_BACKUP_RESULT_FILE invalido"
  printf '%s\n' "$FINAL_DIR" > "$RESULT_FILE"
  chmod 0600 "$RESULT_FILE"
fi

restore_service_state
validate_recovered_services
SERVICES_QUIESCED=false
ERROR_HANDLER_ARMED=false
trap - ERR TERM HUP INT
trap - EXIT TERM HUP INT
echo "[backup] PostgreSQL, ambiente e artefatos presentes validados"
echo "[backup] commit=$GIT_COMMIT revision=$ALEMBIC_CURRENT"
echo "[backup] set=$FINAL_DIR"
echo "[backup] manifest=$FINAL_DIR/manifest.json"
