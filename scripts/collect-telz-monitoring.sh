#!/usr/bin/env bash
set -Eeuo pipefail
umask 027

die() {
  echo "[monitoring][erro] $*" >&2
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

INSTALL_DIR="$(realpath -e "${1:-/opt/telz}")"
SERVICE_USER="${2:-${TELZ_SERVICE_USER:-telz}}"
OUTPUT_DIR="${TELZ_MONITORING_DIR:-/var/lib/telz/monitoring}"
BACKUP_DIR="${TELZ_BACKUP_DIR:-/var/backups/telz}"
LOCK_DIR="${TELZ_MONITORING_LOCK_DIR:-/run/telz-monitoring}"
RELEASES_DIR="${TELZ_RELEASES_DIR:-/var/lib/telz/releases}"
CURRENT_LINK="${TELZ_CURRENT_RELEASE_LINK:-/var/lib/telz/current}"

[[ "$INSTALL_DIR" = /* && "$INSTALL_DIR" != "/" ]] || die "INSTALL_DIR invalido"
[[ -f "$INSTALL_DIR/backend/.env" && ! -L "$INSTALL_DIR/backend/.env" ]] || die "instalacao Telz incompleta"
[[ "$OUTPUT_DIR" = /* && "$OUTPUT_DIR" != "/" ]] || die "TELZ_MONITORING_DIR invalido"
[[ "$LOCK_DIR" = /* && "$LOCK_DIR" != "/" ]] || die "TELZ_MONITORING_LOCK_DIR invalido"
id "$SERVICE_USER" >/dev/null 2>&1 || die "usuario de servico inexistente: $SERVICE_USER"
[[ -x /usr/bin/python3 ]] || die "/usr/bin/python3 nao encontrado"
PG_RESTORE_BIN="$(command -v pg_restore || true)"
[[ -n "$PG_RESTORE_BIN" ]] || die "pg_restore nao encontrado"
PG_RESTORE_BIN="$(realpath -e "$PG_RESTORE_BIN")"
require_root_owned_executable "$PG_RESTORE_BIN"

CODE_DIR="$INSTALL_DIR"
if [[ -e "$CURRENT_LINK" || -L "$CURRENT_LINK" ]]; then
  [[ -L "$CURRENT_LINK" && "$(stat -c '%U' "$CURRENT_LINK")" == "root" ]] || die "current deve ser symlink root-owned"
  [[ -d "$RELEASES_DIR" && ! -L "$RELEASES_DIR" ]] || die "diretorio de releases invalido"
  RELEASES_REAL="$(realpath -e "$RELEASES_DIR")"
  CODE_DIR="$(realpath -e "$CURRENT_LINK")"
  RELEASE_ROOT="$(dirname "$CODE_DIR")"
  RELEASE_ID="$(basename "$RELEASE_ROOT")"
  [[ "$(dirname "$RELEASE_ROOT")" == "$RELEASES_REAL" && "$(basename "$CODE_DIR")" == "app" ]] || \
    die "current aponta fora do layout de releases"
  [[ "$RELEASE_ID" =~ ^[0-9a-f]{40}$ ]] || die "identificador da release invalido"
  for candidate in "$RELEASES_REAL" "$RELEASE_ROOT" "$CODE_DIR" "$CODE_DIR/.telz-release.json"; do
    [[ -e "$candidate" && ! -L "$candidate" && "$(stat -c '%U' "$candidate")" == "root" ]] || \
      die "release ativa possui componente inseguro"
    [[ -z "$(find "$candidate" -maxdepth 0 -perm /022 -print -quit)" ]] || die "release ativa gravavel"
  done
  /usr/bin/python3 - "$CODE_DIR/.telz-release.json" "$RELEASE_ID" "$INSTALL_DIR" <<'PY'
import json
import re
import sys
from pathlib import Path

try:
    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
except Exception:
    raise SystemExit("manifest da release invalido")
if data.get("schema_version") != 2 or data.get("status") != "validated":
    raise SystemExit("release nao validada")
if data.get("git_commit") != sys.argv[2] or not re.fullmatch(r"[0-9a-f]{40}", sys.argv[2]):
    raise SystemExit("commit da release invalido")
if not re.fullmatch(r"[A-Za-z0-9_]+", str(data.get("alembic_revision") or "")):
    raise SystemExit("revision da release invalida")
hash_fields = ("dependency_artifact_sha256", "content_sha256", "python_freeze_sha256", "requirements_sha256", "pnpm_lock_sha256", "public_build_config_sha256")
if any(not re.fullmatch(r"[0-9a-f]{64}", str(data.get(name) or "")) for name in hash_fields):
    raise SystemExit("hash do manifest invalido")
toolchain = data.get("toolchain")
if not isinstance(toolchain, dict) or set(toolchain) != {"python", "pip", "node", "pnpm"}:
    raise SystemExit("toolchain do manifest invalida")
legacy = data.get("legacy_compat")
expected = {"backend/.env": str(Path(sys.argv[3]) / "backend" / ".env")} if sys.argv[2] == "2f1006860b648cf7a4734222da69879256c174e7" else {}
if legacy != expected:
    raise SystemExit("legacy_compat invalido")
PY
else
  [[ -d "$INSTALL_DIR/.git" && ! -L "$INSTALL_DIR/.git" ]] || die "repositorio legado ausente"
fi
[[ -x "$CODE_DIR/.venv/bin/python" && -f "$CODE_DIR/package.json" ]] || die "runtime da release ativa incompleto"

install -d -m 0750 -o root -g "$SERVICE_USER" "$OUTPUT_DIR"
install -d -m 0750 -o root -g root "$LOCK_DIR"
exec 9>"$LOCK_DIR/collector.lock"
flock -n 9 || exit 0

API_URL="${TELZ_API_HEALTH_URL:-http://127.0.0.1:${TELZ_MONITOR_API_PORT:-8000}/health}"
WEB_URL="${TELZ_WEB_HEALTH_URL:-http://127.0.0.1:${TELZ_MONITOR_WEB_PORT:-3000}}"

unit_exists() {
  systemctl list-unit-files "$1.service" --no-legend 2>/dev/null | grep -q "^$1.service"
}

gateway_health_as_service() {
  sudo -u "$SERVICE_USER" -H /usr/bin/python3 - \
    "$INSTALL_DIR/backend/.env" "$INSTALL_DIR" "$CODE_DIR" <<'PY'
import ast
import os
import stat
import sys
from urllib.parse import urlsplit

env_path, install_root, code_root = sys.argv[1:4]
allowed_keys = {"WHATSAPP_GATEWAY_RUNTIME_URL", "WHATSAPP_GATEWAY_RUNTIME_TOKEN"}

def decode_value(raw_value: str) -> str:
    value = raw_value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        try:
            decoded = ast.literal_eval(value)
        except (SyntaxError, ValueError) as exc:
            raise SystemExit("configuracao do runtime WhatsApp invalida") from exc
        if not isinstance(decoded, str):
            raise SystemExit("configuracao do runtime WhatsApp invalida")
        return decoded
    return value

try:
    descriptor = os.open(env_path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    env_stat = os.fstat(descriptor)
    if not stat.S_ISREG(env_stat.st_mode) or not 0 < env_stat.st_size <= 1024 * 1024:
        raise OSError("arquivo de ambiente inseguro")
    with os.fdopen(descriptor, "r", encoding="utf-8") as stream:
        lines = stream.read().splitlines()
except (OSError, UnicodeError) as exc:
    raise SystemExit("nao foi possivel ler a configuracao do runtime WhatsApp") from exc

values: dict[str, str] = {}
for raw_line in lines:
    line = raw_line.strip()
    if not line or line.startswith("#"):
        continue
    if line.startswith("export "):
        line = line[7:].lstrip()
    key, separator, raw_value = line.partition("=")
    key = key.strip()
    if not separator or key not in allowed_keys:
        continue
    if key in values:
        raise SystemExit("configuracao duplicada do runtime WhatsApp")
    values[key] = decode_value(raw_value)

runtime_url = values.get("WHATSAPP_GATEWAY_RUNTIME_URL", "")
runtime_token = values.get("WHATSAPP_GATEWAY_RUNTIME_TOKEN", "")
try:
    parsed = urlsplit(runtime_url)
    port = parsed.port
except ValueError as exc:
    raise SystemExit("URL do runtime WhatsApp invalida") from exc
if (
    parsed.scheme != "http"
    or parsed.hostname not in {"127.0.0.1", "::1", "localhost"}
    or port is None
    or not 1 <= port <= 65535
    or parsed.username is not None
    or parsed.password is not None
    or parsed.path not in {"", "/"}
    or parsed.query
    or parsed.fragment
):
    raise SystemExit("URL do runtime WhatsApp deve usar loopback local")
if (
    not runtime_token
    or runtime_token != runtime_token.strip()
    or len(runtime_token) > 4096
    or any(ord(character) < 33 or ord(character) == 127 for character in runtime_token)
):
    raise SystemExit("token do runtime WhatsApp ausente ou invalido")

normalized_host = "[::1]" if parsed.hostname == "::1" else parsed.hostname
runtime_environment = os.environ.copy()
runtime_environment.update({
    "TELZ_PROJECT_ROOT": install_root,
    "WHATSAPP_GATEWAY_RUNTIME_URL": f"http://{normalized_host}:{port}",
    "WHATSAPP_GATEWAY_RUNTIME_TOKEN": runtime_token,
})
os.execvpe(
    "pnpm",
    ["pnpm", "-C", code_root, "whatsapp-gateway:health"],
    runtime_environment,
)
PY
}

unit_state() {
  if ! unit_exists "$1"; then
    printf 'not-installed'
  elif systemctl is-active --quiet "$1"; then
    printf 'active'
  else
    printf 'inactive'
  fi
}

probe() {
  if "$@" >/dev/null 2>&1; then
    printf 'true'
  else
    printf 'false'
  fi
}

API_SERVICE_STATE="$(unit_state telz-api)"
WEB_SERVICE_STATE="$(unit_state telz-web)"
GATEWAY_SERVICE_STATE="$(unit_state telz-whatsapp-gateway)"
NGINX_OK="$(probe nginx -t)"
API_OK="$(probe curl --fail --silent --show-error --max-time 5 "$API_URL")"
WEB_OK="$(probe curl --fail --silent --show-error --head --max-time 5 "$WEB_URL")"

DB_OK=false
if sudo -u "$SERVICE_USER" -H env TELZ_PROJECT_ROOT="$INSTALL_DIR" bash -c \
  'cd "$1" && exec .venv/bin/python -c '\''from sqlalchemy import text; from backend.database import engine; c = engine.connect(); assert c.execute(text("SELECT 1")).scalar_one() == 1; c.close()'\''' \
  bash "$CODE_DIR" >/dev/null 2>&1; then
  DB_OK=true
fi

GATEWAY_OK=true
if unit_exists telz-whatsapp-gateway; then
  GATEWAY_OK=false
  if gateway_health_as_service >/dev/null 2>&1; then
    GATEWAY_OK=true
  fi
fi

read -r INSTALL_TOTAL INSTALL_USED INSTALL_AVAILABLE INSTALL_PERCENT < <(
  df -P -B1 "$INSTALL_DIR" | awk 'NR == 2 {gsub(/%/, "", $5); print $2, $3, $4, $5}'
)
BACKUP_TOTAL=0
BACKUP_USED=0
BACKUP_AVAILABLE=0
BACKUP_PERCENT=0
if [[ -d "$BACKUP_DIR" ]]; then
  read -r BACKUP_TOTAL BACKUP_USED BACKUP_AVAILABLE BACKUP_PERCENT < <(
    df -P -B1 "$BACKUP_DIR" | awk 'NR == 2 {gsub(/%/, "", $5); print $2, $3, $4, $5}'
  )
fi

export TELZ_MONITOR_TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
export TELZ_MONITOR_API_STATE="$API_SERVICE_STATE"
export TELZ_MONITOR_WEB_STATE="$WEB_SERVICE_STATE"
export TELZ_MONITOR_GATEWAY_STATE="$GATEWAY_SERVICE_STATE"
export TELZ_MONITOR_NGINX_OK="$NGINX_OK"
export TELZ_MONITOR_API_OK="$API_OK"
export TELZ_MONITOR_WEB_OK="$WEB_OK"
export TELZ_MONITOR_DB_OK="$DB_OK"
export TELZ_MONITOR_GATEWAY_OK="$GATEWAY_OK"
export TELZ_MONITOR_INSTALL_DISK="$INSTALL_TOTAL,$INSTALL_USED,$INSTALL_AVAILABLE,$INSTALL_PERCENT"
export TELZ_MONITOR_BACKUP_DISK="$BACKUP_TOTAL,$BACKUP_USED,$BACKUP_AVAILABLE,$BACKUP_PERCENT"
export TELZ_MONITOR_INSTALL_DIR="$INSTALL_DIR"
export TELZ_MONITOR_BACKUP_DIR="$BACKUP_DIR"
export TELZ_MONITOR_OUTPUT_DIR="$OUTPUT_DIR"
export TELZ_MONITOR_SERVICE_USER="$SERVICE_USER"
export TELZ_MONITOR_PG_RESTORE="$PG_RESTORE_BIN"

/usr/bin/python3 - <<'PY'
import hashlib
import hmac
import json
import os
import re
import stat
import subprocess
import tempfile
from datetime import datetime, timezone
from grp import getgrnam
from pathlib import Path


SAFE_ID = re.compile(r"^[A-Za-z0-9._:-]+$")
BACKUP_RUN_ID = re.compile(r"^[0-9]{8}-[0-9]{6}-[0-9]+$")
SHA256_LINE = re.compile(r"^([0-9a-fA-F]{64}) [ *]([A-Za-z0-9._-]+)$")
BACKUP_COMPONENT_KEYS = {
    "database.dump": "database",
    "uploads.tar.gz": "uploads",
    "environment.env": "environment",
    "baileys.tar.gz": "baileys",
}
REQUIRED_BACKUP_COMPONENTS = frozenset({"database.dump", "environment.env"})
BACKUP_METADATA_FILES = frozenset({"manifest.json", "SHA256SUMS"})
FULL_VALIDATION_TTL_SECONDS = 24 * 60 * 60
MAX_METADATA_BYTES = 1_048_576
output_root = Path(os.environ["TELZ_MONITOR_OUTPUT_DIR"])
install_root = Path(os.environ["TELZ_MONITOR_INSTALL_DIR"])
backup_root = Path(os.environ["TELZ_MONITOR_BACKUP_DIR"])
service_gid = getgrnam(os.environ["TELZ_MONITOR_SERVICE_USER"]).gr_gid
pg_restore_bin = Path(os.environ["TELZ_MONITOR_PG_RESTORE"])
generated_at = os.environ["TELZ_MONITOR_TIMESTAMP"]


def ensure_dir(path: Path) -> None:
    path.mkdir(mode=0o750, parents=True, exist_ok=True)
    os.chown(path, 0, service_gid)
    os.chmod(path, 0o750)


def atomic_json(relative: str, payload: dict) -> None:
    target = output_root / relative
    ensure_dir(target.parent)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".tmp-", dir=target.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
            os.fchmod(stream.fileno(), 0o640)
            os.fchown(stream.fileno(), 0, service_gid)
        os.replace(temporary_name, target)
    finally:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass


def flag(name: str) -> bool:
    return os.environ.get(name, "false").lower() == "true"


def disk_values(name: str) -> tuple[int, int, int, int]:
    values = [int(value) for value in os.environ[name].split(",")]
    if len(values) != 4:
        raise ValueError("disk probe invalido")
    return values[0], values[1], values[2], values[3]


def component(key: str, status: str, message_code: str) -> dict:
    return {
        "key": key,
        "status": status,
        "checked_at": generated_at,
        "message_code": message_code,
    }


def service_status(state: str) -> tuple[str, str]:
    if state == "active":
        return "healthy", "ok"
    if state == "not-installed":
        return "unknown", "unreachable"
    return "critical", "inactive"


api_status = ("healthy", "ok") if os.environ["TELZ_MONITOR_API_STATE"] == "active" and flag("TELZ_MONITOR_API_OK") else ("critical", "unreachable")
web_status = ("healthy", "ok") if os.environ["TELZ_MONITOR_WEB_STATE"] == "active" and flag("TELZ_MONITOR_WEB_OK") else ("critical", "unreachable")
nginx_status = ("healthy", "ok") if flag("TELZ_MONITOR_NGINX_OK") else ("critical", "config_invalid")
gateway_service_status = service_status(os.environ["TELZ_MONITOR_GATEWAY_STATE"])
if os.environ["TELZ_MONITOR_GATEWAY_STATE"] == "not-installed":
    gateway_runtime_status = ("unknown", "unreachable")
elif flag("TELZ_MONITOR_GATEWAY_OK"):
    gateway_runtime_status = ("healthy", "ok")
else:
    gateway_runtime_status = ("critical", "unreachable")

health = {
    "schema_version": 1,
    "generated_at": generated_at,
    "components": [
        component("api", *api_status),
        component("web", *web_status),
        component("nginx", *nginx_status),
        component("gateway_service", *gateway_service_status),
        component("gateway_runtime", *gateway_runtime_status),
        component("observer", "healthy", "ok"),
    ],
}
atomic_json("health.json", health)


def tree_metrics(path: Path) -> tuple[int, int]:
    total_bytes = 0
    files = 0
    if path.is_symlink() or not path.is_dir():
        return total_bytes, files
    for candidate in path.rglob("*"):
        try:
            if candidate.is_file() and not candidate.is_symlink():
                total_bytes += candidate.stat().st_size
                files += 1
        except OSError:
            continue
    return total_bytes, files


uploads_root = install_root / "uploads"
uploads_bytes, uploads_files = tree_metrics(uploads_root)
uploads_safe = uploads_root.is_dir() and not uploads_root.is_symlink()
optimized_bytes, optimized_files = tree_metrics(uploads_root / "optimized") if uploads_safe else (0, 0)
baileys_bytes, baileys_files = tree_metrics(install_root / ".runtime" / "baileys")
tenant_bytes = 0
tenant_files = 0
tenants = []
tenant_root = uploads_root / "tenants"
if uploads_safe and tenant_root.is_dir() and not tenant_root.is_symlink():
    for tenant_dir in sorted(tenant_root.iterdir(), key=lambda item: item.name):
        if not tenant_dir.is_dir() or tenant_dir.is_symlink() or not SAFE_ID.fullmatch(tenant_dir.name):
            continue
        size, count = tree_metrics(tenant_dir)
        tenant_bytes += size
        tenant_files += count
        tenants.append({"tenant_id": tenant_dir.name, "bytes": size, "files": count})
legacy_bytes = max(0, uploads_bytes - optimized_bytes - tenant_bytes)
legacy_files = max(0, uploads_files - optimized_files - tenant_files)
total, used, free, used_percent = disk_values("TELZ_MONITOR_INSTALL_DISK")
storage_status = "critical" if used_percent >= 90 else "degraded" if used_percent >= 80 else "healthy"
storage = {
    "schema_version": 1,
    "generated_at": generated_at,
    "status": storage_status,
    "disk": {"total_bytes": total, "used_bytes": used, "free_bytes": free, "usage_percent": used_percent},
    "uploads": {"bytes": uploads_bytes, "files": uploads_files},
    "optimized": {"bytes": optimized_bytes, "files": optimized_files},
    "baileys": {"bytes": baileys_bytes, "files": baileys_files},
    "legacy_unattributed": {"bytes": legacy_bytes, "files": legacy_files},
    "tenants": tenants,
}
atomic_json("storage.json", storage)

atomic_json("gateway.json", {
    "schema_version": 1,
    "generated_at": generated_at,
    "status": gateway_runtime_status[0],
})


def trusted_directory_stat(path: Path):
    try:
        candidate_stat = path.lstat()
    except OSError:
        return None
    if (
        not stat.S_ISDIR(candidate_stat.st_mode)
        or candidate_stat.st_uid != 0
        or candidate_stat.st_mode & 0o022
    ):
        return None
    return candidate_stat


def regular_file_stat(path: Path):
    try:
        candidate_stat = path.lstat()
    except OSError:
        return None
    if (
        not stat.S_ISREG(candidate_stat.st_mode)
        or candidate_stat.st_uid != 0
        or candidate_stat.st_mode & 0o022
    ):
        return None
    return candidate_stat


def utc_timestamp(value: object) -> str | None:
    if not isinstance(value, str) or not value or len(value) > 64:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return value


def read_metadata(path: Path, candidate_stat) -> bytes:
    if candidate_stat is None or candidate_stat.st_size <= 0 or candidate_stat.st_size > MAX_METADATA_BYTES:
        raise ValueError("metadado de backup invalido")
    data = path.read_bytes()
    if len(data) != candidate_stat.st_size:
        raise ValueError("metadado de backup mudou durante leitura")
    return data


def parse_sha256sums(data: bytes) -> dict[str, str]:
    try:
        lines = data.decode("ascii").splitlines()
    except UnicodeDecodeError as exc:
        raise ValueError("checksums invalidos") from exc
    checksums: dict[str, str] = {}
    if not lines:
        raise ValueError("checksums ausentes")
    for line in lines:
        match = SHA256_LINE.fullmatch(line)
        if match is None or match.group(2) in checksums:
            raise ValueError("checksums invalidos")
        checksums[match.group(2)] = match.group(1).lower()
    return checksums


def inspect_backup_set(backup_set: Path, run_id: str, fallback_timestamp: str) -> dict:
    inspection = {
        "quick_valid": False,
        "created_at": fallback_timestamp,
        "declared": set(),
        "sizes": {},
        "fingerprint": "",
        "size_bytes": 0,
        "mtime_ns": 0,
        "manifest_components": {},
        "checksums": {},
    }
    try:
        if trusted_directory_stat(backup_set) is None:
            return inspection

        children = {candidate.name: candidate for candidate in backup_set.iterdir()}
        file_stats = {name: regular_file_stat(candidate) for name, candidate in children.items()}
        for private_name in BACKUP_COMPONENT_KEYS:
            candidate_stat = file_stats.get(private_name)
            if candidate_stat is not None and candidate_stat.st_size > 0:
                inspection["sizes"][private_name] = candidate_stat.st_size

        manifest_stat = file_stats.get("manifest.json")
        checksums_stat = file_stats.get("SHA256SUMS")
        manifest_data = read_metadata(backup_set / "manifest.json", manifest_stat)
        checksums_data = read_metadata(backup_set / "SHA256SUMS", checksums_stat)
        manifest = json.loads(manifest_data.decode("utf-8"))
        if not isinstance(manifest, dict):
            raise ValueError("manifesto invalido")
        if manifest.get("schema_version") != 1 or manifest.get("status") != "validated":
            raise ValueError("manifesto nao validado")
        if manifest.get("backup_id") != run_id:
            raise ValueError("identificador divergente")
        created_at = utc_timestamp(manifest.get("created_at"))
        if created_at is None:
            raise ValueError("timestamp invalido")

        raw_components = manifest.get("components")
        if not isinstance(raw_components, dict):
            raise ValueError("componentes invalidos")
        declared = set(raw_components)
        if not REQUIRED_BACKUP_COMPONENTS.issubset(declared):
            raise ValueError("componentes obrigatorios ausentes")
        if not declared.issubset(BACKUP_COMPONENT_KEYS):
            raise ValueError("componente nao permitido")

        expected_names = BACKUP_METADATA_FILES | declared
        if set(children) != expected_names or any(file_stats[name] is None for name in expected_names):
            raise ValueError("set contem entrada ausente ou nao regular")

        normalized_components = {}
        for private_name in declared:
            descriptor = raw_components.get(private_name)
            candidate_stat = file_stats[private_name]
            if not isinstance(descriptor, dict) or candidate_stat.st_size <= 0:
                raise ValueError("componente invalido")
            declared_size = descriptor.get("size_bytes")
            declared_digest = descriptor.get("sha256")
            if isinstance(declared_size, bool) or not isinstance(declared_size, int):
                raise ValueError("tamanho declarado invalido")
            if declared_size != candidate_stat.st_size:
                raise ValueError("tamanho declarado divergente")
            if not isinstance(declared_digest, str) or re.fullmatch(r"[0-9a-fA-F]{64}", declared_digest) is None:
                raise ValueError("hash declarado invalido")
            normalized_components[private_name] = {
                "size_bytes": declared_size,
                "sha256": declared_digest.lower(),
            }

        checksums = parse_sha256sums(checksums_data)
        if set(checksums) != declared:
            raise ValueError("lista de checksums divergente")

        metadata_rows = [
            {
                "name": name,
                "size_bytes": file_stats[name].st_size,
                "mtime_ns": file_stats[name].st_mtime_ns,
            }
            for name in sorted(expected_names)
        ]
        fingerprint_payload = {
            "files": metadata_rows,
            "manifest": hashlib.sha256(manifest_data).hexdigest(),
            "checksums": hashlib.sha256(checksums_data).hexdigest(),
        }
        inspection.update({
            "quick_valid": True,
            "created_at": created_at,
            "declared": declared,
            "sizes": {name: file_stats[name].st_size for name in declared},
            "fingerprint": hashlib.sha256(
                json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode("ascii")
            ).hexdigest(),
            "size_bytes": sum(row["size_bytes"] for row in metadata_rows),
            "mtime_ns": max(row["mtime_ns"] for row in metadata_rows),
            "manifest_components": normalized_components,
            "checksums": checksums,
        })
    except (OSError, UnicodeDecodeError, ValueError, TypeError, json.JSONDecodeError):
        return inspection
    return inspection


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pg_restore_list_valid(database_dump: Path) -> bool:
    try:
        completed = subprocess.run(
            [str(pg_restore_bin), "--list", str(database_dump)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=300,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return completed.returncode == 0


def full_validate_backup_set(backup_set: Path, inspection: dict) -> bool:
    if not inspection.get("quick_valid"):
        return False
    try:
        for private_name in inspection["declared"]:
            actual_digest = file_sha256(backup_set / private_name)
            if not hmac.compare_digest(actual_digest, inspection["checksums"][private_name]):
                return False
            if not hmac.compare_digest(actual_digest, inspection["manifest_components"][private_name]["sha256"]):
                return False
        return pg_restore_list_valid(backup_set / "database.dump")
    except (OSError, KeyError, TypeError):
        return False


def cache_entry_is_fresh(entry: object, inspection: dict, now: datetime) -> bool:
    if not isinstance(entry, dict) or not isinstance(entry.get("validated"), bool):
        return False
    checked_at = utc_timestamp(entry.get("checked_at"))
    if checked_at is None:
        return False
    try:
        checked = datetime.fromisoformat(checked_at.replace("Z", "+00:00"))
        age_seconds = (now - checked.astimezone(timezone.utc)).total_seconds()
    except (TypeError, ValueError):
        return False
    return (
        0 <= age_seconds < FULL_VALIDATION_TTL_SECONDS
        and hmac.compare_digest(str(entry.get("fingerprint") or ""), inspection["fingerprint"])
        and entry.get("size_bytes") == inspection["size_bytes"]
        and entry.get("mtime_ns") == inspection["mtime_ns"]
    )


def prepare_private_cache(root: Path) -> Path | None:
    cache_root = root / ".cache"
    try:
        if trusted_directory_stat(root) is None:
            return None
        if cache_root.exists() or cache_root.is_symlink():
            cache_stat = cache_root.lstat()
            if (
                not stat.S_ISDIR(cache_stat.st_mode)
                or stat.S_ISLNK(cache_stat.st_mode)
                or cache_stat.st_uid != 0
                or cache_stat.st_mode & 0o022
            ):
                return None
        else:
            cache_root.mkdir(mode=0o700)
        os.chown(cache_root, 0, 0)
        os.chmod(cache_root, 0o700)
        cache_stat = cache_root.lstat()
        if cache_stat.st_uid != 0 or cache_stat.st_mode & 0o077:
            return None
    except OSError:
        return None
    return cache_root


def load_private_cache(cache_root: Path | None) -> dict:
    if cache_root is None:
        return {}
    cache_file = cache_root / "backup-validation.json"
    try:
        cache_stat = cache_file.lstat()
        if (
            not stat.S_ISREG(cache_stat.st_mode)
            or cache_stat.st_uid != 0
            or cache_stat.st_mode & 0o077
            or cache_stat.st_size <= 0
            or cache_stat.st_size > MAX_METADATA_BYTES
        ):
            return {}
        payload = json.loads(cache_file.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {}
    entries = payload.get("entries") if isinstance(payload, dict) else None
    return entries if isinstance(entries, dict) else {}


def save_private_cache(cache_root: Path | None, entries: dict) -> None:
    if cache_root is None:
        return
    cache_file = cache_root / "backup-validation.json"
    try:
        if cache_file.exists() or cache_file.is_symlink():
            cache_stat = cache_file.lstat()
            if (
                not stat.S_ISREG(cache_stat.st_mode)
                or cache_stat.st_uid != 0
                or cache_stat.st_mode & 0o022
            ):
                return
        descriptor, temporary_name = tempfile.mkstemp(prefix=".backup-validation-", dir=cache_root)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump({"schema_version": 1, "entries": entries}, stream, sort_keys=True, separators=(",", ":"))
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
                os.fchmod(stream.fileno(), 0o600)
                os.fchown(stream.fileno(), 0, 0)
            os.replace(temporary_name, cache_file)
        finally:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
    except OSError:
        return


def public_backup_components(inspection: dict, validated: bool) -> list[dict]:
    visible = REQUIRED_BACKUP_COMPONENTS | set(inspection.get("declared", set())) | set(inspection.get("sizes", {}))
    return [
        {
            "key": public_key,
            "status": "healthy" if validated else "critical",
            "size_bytes": max(0, int(inspection.get("sizes", {}).get(private_name, 0))),
            "validated": validated,
        }
        for private_name, public_key in BACKUP_COMPONENT_KEYS.items()
        if private_name in visible
    ]


def existing_backup_entry_ids(root: Path) -> set[str]:
    try:
        if trusted_directory_stat(root) is None:
            return set()
        return {
            candidate.name
            for candidate in root.iterdir()
            if candidate.name != "latest"
            and not candidate.name.startswith(".")
            and BACKUP_RUN_ID.fullmatch(candidate.name)
        }
    except OSError:
        return set()


def remove_stale_backup_snapshots(snapshot_root: Path, active_run_ids: set[str]) -> None:
    try:
        snapshot_stat = snapshot_root.lstat()
        if not stat.S_ISDIR(snapshot_stat.st_mode):
            return
        candidates = list(snapshot_root.glob("*.json"))
    except OSError:
        return
    for candidate in candidates:
        run_id = candidate.stem
        if BACKUP_RUN_ID.fullmatch(run_id) and run_id not in active_run_ids:
            try:
                candidate.unlink()
            except OSError:
                continue


now = datetime.now(timezone.utc)
checked_at = now.isoformat(timespec="seconds").replace("+00:00", "Z")
cache_root = prepare_private_cache(output_root)
cache_entries = load_private_cache(cache_root)
for run_id in sorted(existing_backup_entry_ids(backup_root)):
    backup_set = backup_root / run_id
    inspection = inspect_backup_set(backup_set, run_id, generated_at)
    valid = False
    if inspection["quick_valid"]:
        cached = cache_entries.get(run_id)
        if cache_entry_is_fresh(cached, inspection, now):
            valid = cached["validated"]
        else:
            valid = full_validate_backup_set(backup_set, inspection)
            cache_entries[run_id] = {
                "fingerprint": inspection["fingerprint"],
                "size_bytes": inspection["size_bytes"],
                "mtime_ns": inspection["mtime_ns"],
                "checked_at": checked_at,
                "validated": valid,
            }
    else:
        cache_entries.pop(run_id, None)

    snapshot = {
        "schema_version": 1,
        "run_id": run_id,
        "generated_at": inspection["created_at"],
        "started_at": inspection["created_at"],
        "finished_at": inspection["created_at"],
        "status": "healthy" if valid else "critical",
        "components": public_backup_components(inspection, valid),
    }
    if not valid:
        snapshot.update({"failure_phase": "validation", "failure_code": "integrity_failed"})
    atomic_json(f"backups/{run_id}.json", snapshot)

active_run_ids = existing_backup_entry_ids(backup_root)
remove_stale_backup_snapshots(output_root / "backups", active_run_ids)
cache_entries = {
    run_id: entry
    for run_id, entry in cache_entries.items()
    if run_id in active_run_ids and BACKUP_RUN_ID.fullmatch(run_id) and isinstance(entry, dict)
}
save_private_cache(cache_root, cache_entries)
PY

echo "[monitoring] health, storage, gateway e backups sanitizados atualizados"
