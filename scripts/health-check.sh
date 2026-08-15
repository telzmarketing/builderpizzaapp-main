#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

die() {
  echo "[health][erro] $*" >&2
  exit 1
}

require_root_owned_executable() {
  local candidate="$1"
  [[ -x "$candidate" && ! -L "$candidate" ]] || die "helper operacional invalido: $candidate"
  [[ "$(stat -c '%U' "$candidate")" == "root" ]] || die "helper deve pertencer a root: $candidate"
  [[ -z "$(find "$candidate" -maxdepth 0 -perm /022 -print -quit)" ]] || \
    die "helper nao pode ser gravavel por grupo/outros: $candidate"
}

[[ "${EUID:-$(id -u)}" -eq 0 ]] || die "execute como root"
SCRIPT_PATH="$(realpath -e "$0")"
require_root_owned_executable "$SCRIPT_PATH"

INSTALL_DIR="$(realpath -e "${1:-${APP_DIR:-/opt/telz}}")"
SERVICE_USER="${TELZ_SERVICE_USER:-telz}"
RELEASES_DIR="${TELZ_RELEASES_DIR:-/var/lib/telz/releases}"
CURRENT_LINK="${TELZ_CURRENT_RELEASE_LINK:-/var/lib/telz/current}"
[[ "$INSTALL_DIR" = /* && "$INSTALL_DIR" != "/" ]] || die "INSTALL_DIR invalido"
[[ -f "$INSTALL_DIR/backend/.env" && ! -L "$INSTALL_DIR/backend/.env" ]] || die "ambiente persistente Telz incompleto"
id "$SERVICE_USER" >/dev/null 2>&1 || die "usuario de servico inexistente: $SERVICE_USER"
[[ -x /usr/bin/python3 ]] || die "/usr/bin/python3 nao encontrado"

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

CODE_DIR="$INSTALL_DIR"
RELEASE_COMMIT=""
RELEASE_REVISION=""
if [[ -e "$CURRENT_LINK" || -L "$CURRENT_LINK" ]]; then
  [[ -L "$CURRENT_LINK" && "$(stat -c '%U' "$CURRENT_LINK")" == "root" ]] || \
    die "current deve ser symlink pertencente a root"
  CODE_DIR="$(validate_release_path "$CURRENT_LINK")"
  readarray -t RELEASE_VALUES < <(/usr/bin/python3 - "$CODE_DIR/.telz-release.json" "$(basename "$(dirname "$CODE_DIR")")" "$INSTALL_DIR" <<'PY'
import json
import os
import re
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
persistent = Path(sys.argv[3]).resolve(strict=True)
expected_legacy = {"backend/.env": str(persistent / "backend" / ".env")} if commit == "2f1006860b648cf7a4734222da69879256c174e7" else {}
legacy_compat = data.get("legacy_compat")
if legacy_compat != expected_legacy:
    raise SystemExit("legacy_compat nao autorizado")
allowed_external = {}
if legacy_compat:
    allowed_external = {
        root / "backend" / ".env": persistent / "backend" / ".env",
    }
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
print(commit)
print(revision)
PY
  )
  [[ "${#RELEASE_VALUES[@]}" -eq 2 ]] || die "manifest da release ativa invalido"
  RELEASE_COMMIT="${RELEASE_VALUES[0]}"
  RELEASE_REVISION="${RELEASE_VALUES[1]}"
  for critical_path in \
    .venv/bin/python .venv/bin/alembic backend/alembic.ini \
    dist/server/node-build.mjs dist/spa/index.html server/whatsapp-gateway-runtime.mjs; do
    candidate="$CODE_DIR/$critical_path"
    [[ -f "$candidate" && ! -L "$candidate" && "$(stat -c '%U' "$candidate")" == "root" ]] || \
      die "artefato critico da release invalido: $critical_path"
    [[ -z "$(find "$candidate" -maxdepth 0 -perm /022 -print -quit)" ]] || \
      die "artefato critico da release gravavel: $critical_path"
  done
fi
[[ -x "$CODE_DIR/.venv/bin/python" && -x "$CODE_DIR/.venv/bin/alembic" ]] || die "runtime da release ativa incompleto"

database_revisions_from_active() {
  sudo -u "$SERVICE_USER" -H env TELZ_PROJECT_ROOT="$INSTALL_DIR" \
    "$CODE_DIR/.venv/bin/python" - "$CODE_DIR" <<'PY'
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

API_URL="${API_URL:-http://127.0.0.1:${TELZ_HEALTH_API_PORT:-8000}/health}"
WEB_URL="${WEB_URL:-http://127.0.0.1:${TELZ_HEALTH_WEB_PORT:-3000}}"
MONITOR_DIR="${TELZ_MONITORING_DIR:-/var/lib/telz/monitoring}"
MONITOR_MAX_AGE_SECONDS="${TELZ_MONITOR_MAX_AGE_SECONDS:-180}"
REQUIRE_PUBLIC_HTTPS="${TELZ_REQUIRE_PUBLIC_HTTPS:-false}"
PUBLIC_HEALTH_CANDIDATE="${TELZ_PUBLIC_HEALTH_URL:-${PUBLIC_HEALTH_URL:-}}"

case "$REQUIRE_PUBLIC_HTTPS" in
  true|false) ;;
  *) die "TELZ_REQUIRE_PUBLIC_HTTPS deve ser true ou false" ;;
esac

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

normalize_public_health_url() {
  /usr/bin/python3 - "$INSTALL_DIR/backend/.env" "$1" <<'PY'
import ast
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


def read_env(path: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, raw_value = line.partition("=")
        if not separator:
            continue
        value = raw_value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            try:
                value = str(ast.literal_eval(value))
            except (SyntaxError, ValueError):
                continue
        values[key.strip()] = value
    return values


candidate = sys.argv[2].strip()
if not candidate:
    env = read_env(sys.argv[1])
    platform_hosts = re.split(r"[,\s]+", env.get("TENANT_DOMAINS_PLATFORM_HOSTNAMES", "").strip())
    platform_host = next((item.strip().lower().rstrip(".") for item in platform_hosts if item.strip()), "")
    if platform_host:
        candidate = f"https://{platform_host}/health"
    else:
        public_store = env.get("PUBLIC_STORE_URL", "").strip()
        if public_store:
            origin = urlsplit(public_store)
            if origin.scheme.lower() == "https" and origin.hostname:
                netloc = origin.hostname if origin.port in {None, 443} else f"{origin.hostname}:{origin.port}"
                candidate = urlunsplit(("https", netloc, "/health", "", ""))

if not candidate:
    raise SystemExit("URL publica HTTPS nao configurada")

parsed = urlsplit(candidate)
if (
    parsed.scheme.lower() != "https"
    or not parsed.hostname
    or parsed.username is not None
    or parsed.password is not None
    or parsed.query
    or parsed.fragment
    or parsed.path.rstrip("/") != "/health"
):
    raise SystemExit("URL publica deve usar https e o caminho /health, sem credenciais, query ou fragmento")
try:
    port = parsed.port
except ValueError as exc:
    raise SystemExit("porta da URL publica invalida") from exc
host = parsed.hostname.lower().rstrip(".")
if not re.fullmatch(r"[a-z0-9.-]+", host) or ".." in host or host.startswith("-"):
    raise SystemExit("hostname publico invalido")
netloc = host if port in {None, 443} else f"{host}:{port}"
print(urlunsplit(("https", netloc, "/health", "", "")))
PY
}

validate_health_response() {
  /usr/bin/python3 - "$1" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
data = payload.get("data") if isinstance(payload, dict) else None
status = data.get("status") if isinstance(data, dict) else payload.get("status") if isinstance(payload, dict) else None
is_envelope = isinstance(data, dict) or (isinstance(payload, dict) and "success" in payload)
valid = payload.get("success") is True and status in {"ok", "healthy"} if is_envelope else status in {"ok", "healthy"}
if not valid:
    raise SystemExit("resposta de health da API invalida")
PY
}

validate_monitor_snapshot() {
  /usr/bin/python3 - "$1" <<'PY'
import json
import sys
from pathlib import Path

try:
    payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
except Exception:
    raise SystemExit("snapshot operacional invalido")
components = payload.get("components") if isinstance(payload, dict) else None
if payload.get("schema_version") != 1 or not isinstance(components, list) or not components:
    raise SystemExit("snapshot operacional fora do contrato")
for component in components:
    if not isinstance(component, dict) or component.get("status") not in {"healthy", "degraded", "unknown", "critical"}:
        raise SystemExit("componente operacional invalido")
    if component.get("status") == "critical":
        raise SystemExit("snapshot possui componente critico")
PY
}

echo "[health] services"
systemctl is-active --quiet telz-api
systemctl is-active --quiet telz-web

GATEWAY_INSTALLED=false
if unit_exists telz-whatsapp-gateway; then
  GATEWAY_INSTALLED=true
  systemctl is-active --quiet telz-whatsapp-gateway
fi

echo "[health] Nginx"
nginx -t >/dev/null

API_RESPONSE="$(mktemp /tmp/telz-health-api.XXXXXX)"
PUBLIC_RESPONSE=""
cleanup() {
  if [[ -n "${API_RESPONSE:-}" && "$API_RESPONSE" == /tmp/telz-health-api.* ]]; then
    rm -f -- "$API_RESPONSE"
  fi
  if [[ -n "${PUBLIC_RESPONSE:-}" && "$PUBLIC_RESPONSE" == /tmp/telz-health-public.* ]]; then
    rm -f -- "$PUBLIC_RESPONSE"
  fi
}
trap cleanup EXIT

echo "[health] API local"
curl --fail --silent --show-error --max-time 10 --output "$API_RESPONSE" "$API_URL"
validate_health_response "$API_RESPONSE"

echo "[health] web local"
curl --fail --silent --show-error --head --max-time 10 "$WEB_URL" >/dev/null

echo "[health] PostgreSQL SELECT 1"
sudo -u "$SERVICE_USER" -H env TELZ_PROJECT_ROOT="$INSTALL_DIR" bash -c \
  'cd "$1" && exec .venv/bin/python -c '\''from sqlalchemy import text; from backend.database import engine; c = engine.connect(); assert c.execute(text("SELECT 1")).scalar_one() == 1; c.close()'\''' \
  bash "$CODE_DIR"

if [[ -n "${TELZ_ALEMBIC_TARGET:-}" || -n "$RELEASE_REVISION" ]]; then
  mapfile -t DB_CURRENTS < <(
    database_revisions_from_active
  )
  [[ "${#DB_CURRENTS[@]}" -eq 1 ]] || die "banco deve possuir exatamente uma revision Alembic"
  if [[ -n "${TELZ_ALEMBIC_TARGET:-}" ]]; then
    [[ "${DB_CURRENTS[0]}" == "$TELZ_ALEMBIC_TARGET" ]] || \
      die "revision Alembic atual difere de TELZ_ALEMBIC_TARGET"
  fi
  if [[ -n "$RELEASE_REVISION" ]]; then
    mapfile -t CODE_HEADS < <(
      sudo -u "$SERVICE_USER" -H env TELZ_PROJECT_ROOT="$INSTALL_DIR" bash -c \
        'cd "$1" && exec .venv/bin/alembic -c backend/alembic.ini heads' bash "$CODE_DIR" | awk 'NF {print $1}'
    )
    [[ "${#CODE_HEADS[@]}" -eq 1 && "${CODE_HEADS[0]}" == "$RELEASE_REVISION" ]] || \
      die "head Alembic da release diverge do manifest"
    [[ "$RELEASE_REVISION" == "${DB_CURRENTS[0]}" || \
       "$RELEASE_REVISION:${DB_CURRENTS[0]}" == "20260816_master_completion:20260818_platform_operations" || \
       "$RELEASE_REVISION:${DB_CURRENTS[0]}" == "20260817_platform_wave0:20260818_platform_operations" ]] || \
      die "release ativa nao e compativel com o schema do banco"
  fi
fi

if [[ "$GATEWAY_INSTALLED" == "true" ]]; then
  echo "[health] WhatsApp Gateway runtime"
  gateway_health_as_service >/dev/null
fi

if unit_exists telz-monitoring; then
  echo "[health] observador operacional"
  systemctl is-active --quiet telz-monitoring.timer
  systemctl start telz-monitoring.service
  SNAPSHOT="$MONITOR_DIR/health.json"
  [[ -f "$SNAPSHOT" && ! -L "$SNAPSHOT" ]] || die "snapshot health.json ausente"
  [[ "$(stat -c '%U:%G' "$SNAPSHOT")" == "root:$SERVICE_USER" ]] || die "ownership do snapshot invalido"
  [[ "$(stat -c '%a' "$SNAPSHOT")" == "640" ]] || die "permissao do snapshot invalida"
  sudo -u "$SERVICE_USER" -H test -r "$SNAPSHOT" || die "API nao consegue ler o snapshot"
  SNAPSHOT_AGE="$(( $(date +%s) - $(stat -c '%Y' "$SNAPSHOT") ))"
  [[ "$SNAPSHOT_AGE" -ge 0 && "$SNAPSHOT_AGE" -le "$MONITOR_MAX_AGE_SECONDS" ]] || die "snapshot operacional desatualizado"
  validate_monitor_snapshot "$SNAPSHOT" || die "snapshot operacional possui falha critica"
fi

if [[ -n "$PUBLIC_HEALTH_CANDIDATE" || "$REQUIRE_PUBLIC_HTTPS" == "true" ]]; then
  PUBLIC_HEALTH_URL="$(normalize_public_health_url "$PUBLIC_HEALTH_CANDIDATE")" || \
    die "nao foi possivel determinar uma URL publica HTTPS segura"
  PUBLIC_RESPONSE="$(mktemp /tmp/telz-health-public.XXXXXX)"
  echo "[health] endpoint publico HTTPS"
  curl --proto '=https' --tlsv1.2 --fail --silent --show-error --max-time 15 \
    --output "$PUBLIC_RESPONSE" "$PUBLIC_HEALTH_URL"
  validate_health_response "$PUBLIC_RESPONSE"
fi

rm -f -- "$API_RESPONSE"
API_RESPONSE=""
if [[ -n "$PUBLIC_RESPONSE" ]]; then
  rm -f -- "$PUBLIC_RESPONSE"
  PUBLIC_RESPONSE=""
fi
trap - EXIT
echo "[health] Telz OK"
