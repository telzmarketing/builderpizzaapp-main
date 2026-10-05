#!/usr/bin/env bash
# Apply a sealed Telz release that an operator copied to the VPS by SCP.
# The package is intentionally data-only: this helper is installed/executed by
# root from a trusted checkout, and never accepts credentials in its manifest.
set -Eeuo pipefail
umask 077

die() {
  echo "[manual-deploy][erro] $*" >&2
  exit 1
}

require_root_safe_file() {
  local candidate="$1"
  [[ -f "$candidate" && ! -L "$candidate" ]] || die "arquivo invalido: $candidate"
  [[ "$(stat -c '%U:%G:%h' "$candidate")" == "root:root:1" ]] || die "arquivo deve pertencer somente a root: $candidate"
  [[ -z "$(find "$candidate" -maxdepth 0 -perm /022 -print -quit)" ]] || die "arquivo gravavel por grupo/outros: $candidate"
}

[[ "${EUID:-$(id -u)}" -eq 0 ]] || die "execute como root"
SOURCE_SCRIPT="$(realpath -e -- "$0")"
require_root_safe_file "$SOURCE_SCRIPT"
[[ -x "$SOURCE_SCRIPT" ]] || die "helper deve ser executavel e root-owned"

ARTIFACT_INPUT="${1:-}"
INSTALL_INPUT="${2:-/opt/telz}"
[[ "$ARTIFACT_INPUT" = /* && ! -L "$ARTIFACT_INPUT" ]] || die "diretorio de artefatos deve ser absoluto e nao pode ser symlink"
ARTIFACT_DIR="$(realpath -e -- "$ARTIFACT_INPUT")"
[[ -d "$ARTIFACT_DIR" && ! -L "$ARTIFACT_DIR" && "$ARTIFACT_DIR" != "/" ]] || die "diretorio de artefatos invalido"
[[ "$(stat -c '%U:%G' "$ARTIFACT_DIR")" == "root:root" ]] || die "diretorio de artefatos deve pertencer a root"
[[ -z "$(find "$ARTIFACT_DIR" -maxdepth 0 -perm /022 -print -quit)" ]] || die "diretorio de artefatos gravavel por grupo/outros"
[[ -z "$(find "$ARTIFACT_DIR" -xdev -type l -print -quit)" ]] || die "diretorio de artefatos nao pode conter symlinks"
[[ -z "$(find "$ARTIFACT_DIR" -xdev ! -type d ! -type f -print -quit)" ]] || die "diretorio de artefatos contem tipo especial"
[[ -z "$(find "$ARTIFACT_DIR" -mindepth 1 -type d -print -quit)" ]] || die "diretorio de artefatos nao pode conter subdiretorios"
[[ -z "$(find "$ARTIFACT_DIR" -xdev ! -user root -print -quit)" ]] || die "artefatos devem pertencer integralmente a root"
[[ -z "$(find "$ARTIFACT_DIR" -xdev -perm /022 -print -quit)" ]] || die "artefatos nao podem ser gravaveis por grupo/outros"

INSTALL_DIR="$(realpath -e -- "$INSTALL_INPUT")"
[[ "$INSTALL_DIR" = /* && "$INSTALL_DIR" != "/" && -d "$INSTALL_DIR/.git" ]] || die "INSTALL_DIR invalido"

MANIFEST_NAME="telz-manual-manifest.json"
OPERATION_NAME="operation-bundle.tar.gz"
TARGET_NAME="target-source.tar.gz"
PREVIOUS_NAME="previous-source.tar.gz"
DEPENDENCY_NAME="dependency-bundle.tar.gz"
MANIFEST="$ARTIFACT_DIR/$MANIFEST_NAME"
require_root_safe_file "$MANIFEST"
for filename in "$OPERATION_NAME" "$TARGET_NAME" "$PREVIOUS_NAME" "$DEPENDENCY_NAME"; do
  require_root_safe_file "$ARTIFACT_DIR/$filename"
done

mapfile -t package_files < <(cd "$ARTIFACT_DIR" && find . -maxdepth 1 -type f -printf '%f\n' | LC_ALL=C sort)
expected_files=("$DEPENDENCY_NAME" "$MANIFEST_NAME" "$OPERATION_NAME" "$PREVIOUS_NAME" "$TARGET_NAME")
mapfile -t expected_files < <(printf '%s\n' "${expected_files[@]}" | LC_ALL=C sort)
[[ "$(printf '%s\n' "${package_files[@]}")" == "$(printf '%s\n' "${expected_files[@]}")" ]] || die "diretorio de artefatos contem arquivos inesperados"

mapfile -t manifest_values < <(/usr/bin/python3 - "$MANIFEST" "$OPERATION_NAME" "$TARGET_NAME" "$PREVIOUS_NAME" "$DEPENDENCY_NAME" <<'PY'
import json, re, sys
from pathlib import Path

names = list(sys.argv[2:])
def no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"chave JSON duplicada: {key}")
        result[key] = value
    return result

try:
    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"), object_pairs_hook=no_duplicates)
    expected = {"schema_version", "target_commit", "previous_commit", "alembic_target", "public_health_url", "artifacts"}
    if set(data) != expected or data["schema_version"] != 1:
        raise ValueError("schema do manifest invalido")
    if not isinstance(data["artifacts"], dict) or set(data["artifacts"]) != set(names):
        raise ValueError("artefatos do manifest invalidos")
    if not re.fullmatch(r"[0-9a-f]{40}", str(data["target_commit"])):
        raise ValueError("target_commit invalido")
    if not re.fullmatch(r"[0-9a-f]{40}", str(data["previous_commit"])):
        raise ValueError("previous_commit invalido")
    if data["target_commit"] == data["previous_commit"]:
        raise ValueError("target_commit deve diferir do previous_commit")
    if not re.fullmatch(r"[A-Za-z0-9_]+", str(data["alembic_target"])):
        raise ValueError("alembic_target invalido")
    if data["public_health_url"] != "https://erp.telz.com.br/health":
        raise ValueError("public_health_url nao aprovada")
    for name in names:
        artifact = data["artifacts"][name]
        if not isinstance(artifact, dict) or set(artifact) != {"sha256"} or not re.fullmatch(r"[0-9a-f]{64}", str(artifact["sha256"])):
            raise ValueError(f"hash invalido para {name}")
except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
    raise SystemExit(f"manifest invalido: {error}")

print(data["target_commit"])
print(data["previous_commit"])
print(data["alembic_target"])
print(data["public_health_url"])
for name in names:
    print(data["artifacts"][name]["sha256"])
PY
)
[[ "${#manifest_values[@]}" -eq 8 ]] || die "manifest nao produziu os campos esperados"
TARGET_COMMIT="${manifest_values[0]}"
PREVIOUS_COMMIT="${manifest_values[1]}"
ALEMBIC_TARGET="${manifest_values[2]}"
PUBLIC_HEALTH_URL="${manifest_values[3]}"
OPERATION_SHA="${manifest_values[4]}"
TARGET_SHA="${manifest_values[5]}"
PREVIOUS_SHA="${manifest_values[6]}"
DEPENDENCY_SHA="${manifest_values[7]}"

for pair in "$OPERATION_NAME:$OPERATION_SHA" "$TARGET_NAME:$TARGET_SHA" "$PREVIOUS_NAME:$PREVIOUS_SHA" "$DEPENDENCY_NAME:$DEPENDENCY_SHA"; do
  filename="${pair%%:*}"
  expected_sha="${pair#*:}"
  actual_sha="$(sha256sum "$ARTIFACT_DIR/$filename" | awk '{print $1}')"
  [[ "$actual_sha" == "$expected_sha" ]] || die "hash divergente: $filename"
done

active_commit() {
  local active_app
  if test -L /var/lib/telz/current; then
    active_app="$(readlink -f /var/lib/telz/current)"
    /usr/bin/python3 - "$active_app/.telz-release.json" <<'PY'
import json, re, sys
from pathlib import Path
commit = str(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")).get("git_commit") or "")
if not re.fullmatch(r"[0-9a-f]{40}", commit):
    raise SystemExit("manifest ativo invalido")
print(commit)
PY
  else
    sudo -u telz -H git -C "$INSTALL_DIR" rev-parse HEAD
  fi
}
ACTIVE_COMMIT="$(active_commit)"
[[ "$ACTIVE_COMMIT" == "$PREVIOUS_COMMIT" ]] || die "release ativa nao corresponde ao previous_commit do manifest"

validate_operation_archive() {
  /usr/bin/python3 - "$1" <<'PY'
import sys, tarfile
from pathlib import PurePosixPath
expected = {
    "scripts/update-telz.sh", "scripts/backup-telz.sh", "scripts/health-check.sh",
    "scripts/collect-telz-monitoring.sh", "scripts/restore-telz.sh", "scripts/rollback-telz.sh",
    "scripts/finish-ssl.sh", "scripts/build-telz-release.sh",
    "installer/templates/telz-api.service", "installer/templates/telz-web.service",
    "installer/templates/telz-whatsapp-gateway.service", "installer/templates/telz-monitoring.service",
    "installer/templates/telz-monitoring.timer",
}
seen = set()
try:
    with tarfile.open(sys.argv[1], "r:gz") as archive:
        for member in archive.getmembers():
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts or member.issym() or member.islnk():
                raise ValueError("bundle contem caminho ou link inseguro")
            if member.isdir():
                continue
            if not member.isreg() or member.name not in expected or member.name in seen:
                raise ValueError("bundle contem entrada nao permitida ou duplicada")
            seen.add(member.name)
    if seen != expected:
        raise ValueError("bundle operacional incompleto")
except (tarfile.TarError, ValueError) as error:
    raise SystemExit(f"bundle operacional invalido: {error}")
PY
}
validate_operation_archive "$ARTIFACT_DIR/$OPERATION_NAME"

install -d -m 0700 -o root -g root /var/lib/telz/incoming
BUNDLE_STAGE="$(mktemp -d /var/lib/telz/manual-operation.XXXXXX)"
INCOMING_FILES=()
cleanup() {
  rm -f -- "${INCOMING_FILES[@]:-}" || true
  [[ "${BUNDLE_STAGE:-}" == /var/lib/telz/manual-operation.* ]] && rm -rf -- "$BUNDLE_STAGE" || true
}
trap cleanup EXIT

promote() {
  local filename="$1" expected_sha="$2" destination
  destination="/var/lib/telz/incoming/$filename"
  [[ ! -e "$destination" && ! -L "$destination" ]] || die "artefato de entrada ja existe: $destination"
  install -m 0400 -o root -g root "$ARTIFACT_DIR/$filename" "$destination"
  INCOMING_FILES+=("$destination")
  [[ "$(sha256sum "$destination" | awk '{print $1}')" == "$expected_sha" ]] || die "hash divergente apos promover: $filename"
}
promote "$OPERATION_NAME" "$OPERATION_SHA"
promote "$TARGET_NAME" "$TARGET_SHA"
promote "$PREVIOUS_NAME" "$PREVIOUS_SHA"
promote "$DEPENDENCY_NAME" "$DEPENDENCY_SHA"

tar -xzf "/var/lib/telz/incoming/$OPERATION_NAME" -C "$BUNDLE_STAGE" --no-same-owner --no-same-permissions
chown -R root:root "$BUNDLE_STAGE"
find "$BUNDLE_STAGE" -type d -exec chmod 0555 {} +
find "$BUNDLE_STAGE/scripts" -type f -exec chmod 0555 {} +
find "$BUNDLE_STAGE/installer" -type f -exec chmod 0444 {} +
for script in "$BUNDLE_STAGE"/scripts/*.sh; do bash -n "$script"; done

env \
  TELZ_SERVICE_USER=telz \
  TELZ_EXPECTED_COMMIT="$TARGET_COMMIT" \
  TELZ_PREVIOUS_COMMIT="$PREVIOUS_COMMIT" \
  TELZ_ALEMBIC_TARGET="$ALEMBIC_TARGET" \
  TELZ_OPERATION_BUNDLE_DIR="$BUNDLE_STAGE" \
  TELZ_SOURCE_ARCHIVE="/var/lib/telz/incoming/$TARGET_NAME" \
  TELZ_SOURCE_ARCHIVE_SHA256="$TARGET_SHA" \
  TELZ_PREVIOUS_SOURCE_ARCHIVE="/var/lib/telz/incoming/$PREVIOUS_NAME" \
  TELZ_PREVIOUS_SOURCE_ARCHIVE_SHA256="$PREVIOUS_SHA" \
  TELZ_DEPENDENCY_ARCHIVE="/var/lib/telz/incoming/$DEPENDENCY_NAME" \
  TELZ_DEPENDENCY_ARCHIVE_SHA256="$DEPENDENCY_SHA" \
  TELZ_REQUIRE_PUBLIC_HTTPS=true \
  TELZ_PUBLIC_HEALTH_URL="$PUBLIC_HEALTH_URL" \
  RUN_TESTS=false \
  "$BUNDLE_STAGE/scripts/update-telz.sh" "$INSTALL_DIR"

ACTIVE_APP="$(readlink -f /var/lib/telz/current)"
[[ "$ACTIVE_APP" == "/var/lib/telz/releases/$TARGET_COMMIT/app" ]] || die "release promovida divergiu do target_commit"
/usr/bin/python3 - "$ACTIVE_APP/.telz-release.json" "$TARGET_COMMIT" "$ALEMBIC_TARGET" "$DEPENDENCY_SHA" <<'PY'
import json, sys
from pathlib import Path
data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if not (data.get("schema_version") == 2 and data.get("status") == "validated" and
        data.get("git_commit") == sys.argv[2] and data.get("alembic_revision") == sys.argv[3] and
        data.get("dependency_artifact_sha256") == sys.argv[4]):
    raise SystemExit("manifest da release promovida invalido")
PY
echo "[manual-deploy] concluido release=$TARGET_COMMIT revision=$ALEMBIC_TARGET"
