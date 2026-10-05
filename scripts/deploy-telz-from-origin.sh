#!/usr/bin/env bash
# Build a verified, local delivery set from an explicitly approved origin SHA.
# This is intentionally a root-owned helper.  It never runs source code from
# the checkout: dependency resolution runs as the isolated build account and
# the existing hardened updater remains responsible for backup/migration/
# release activation/recovery.
set -Eeuo pipefail
umask 077

die() {
  echo "[origin-deploy][erro] $*" >&2
  exit 1
}

require_root_owned_file() {
  local candidate="$1"
  [[ -f "$candidate" && ! -L "$candidate" ]] || die "arquivo invalido: $candidate"
  [[ "$(stat -c '%U:%G:%h' "$candidate")" == "root:root:1" ]] || die "arquivo deve ser root:root sem hardlinks: $candidate"
  [[ -z "$(find "$candidate" -maxdepth 0 -perm /022 -print -quit)" ]] || die "arquivo gravavel por grupo/outros: $candidate"
}

require_root_owned_executable() {
  require_root_owned_file "$1"
  [[ -x "$1" ]] || die "arquivo deve ser executavel: $1"
}

as_service() {
  sudo -u "$SERVICE_USER" -H -- "$@"
}

[[ "${EUID:-$(id -u)}" -eq 0 ]] || die "execute como root"
SOURCE_SCRIPT="$(realpath -e -- "$0")"
require_root_owned_executable "$SOURCE_SCRIPT"

# Avoid executing this helper from a path that a later operational update can
# replace while this process is still running.
if [[ "${TELZ_ORIGIN_DEPLOY_REEXEC:-false}" != "true" ]]; then
  TEMP_SCRIPT="$(mktemp /tmp/telz-origin-deploy.XXXXXX)"
  install -m 0700 -o root -g root "$SOURCE_SCRIPT" "$TEMP_SCRIPT"
  exec env TELZ_ORIGIN_DEPLOY_REEXEC=true TELZ_ORIGIN_DEPLOY_TEMP_SCRIPT="$TEMP_SCRIPT" bash "$TEMP_SCRIPT" "$@"
fi

cleanup() {
  [[ -n "${TELZ_ORIGIN_DEPLOY_TEMP_SCRIPT:-}" && "$TELZ_ORIGIN_DEPLOY_TEMP_SCRIPT" == /tmp/telz-origin-deploy.* ]] && rm -f -- "$TELZ_ORIGIN_DEPLOY_TEMP_SCRIPT"
  [[ -n "${STAGE_DIR:-}" && "$STAGE_DIR" == /var/lib/telz/origin-deploy.* && -d "$STAGE_DIR" ]] && rm -rf -- "$STAGE_DIR"
}
trap cleanup EXIT

TARGET_COMMIT="${1:-}"
INSTALL_INPUT="${2:-/opt/telz}"
BRANCH="main"
SERVICE_USER="${TELZ_SERVICE_USER:-telz}"
BUILD_USER="${TELZ_BUILD_USER:-telz-build}"
BUILD_GROUP="${TELZ_BUILD_GROUP:-telz-build}"
ALEMBIC_TARGET="${TELZ_ALEMBIC_TARGET:-20261004_tenant_upload_ownership_contract}"
PUBLIC_HEALTH_URL="https://erp.telz.com.br/health"

[[ "$TARGET_COMMIT" =~ ^[0-9a-f]{40}$ ]] || die "informe o SHA-1 completo do commit alvo"
[[ "$INSTALL_INPUT" = /* && "$INSTALL_INPUT" != "/" && ! -L "$INSTALL_INPUT" ]] || die "INSTALL_DIR invalido"
INSTALL_DIR="$(realpath -e -- "$INSTALL_INPUT")"
[[ -d "$INSTALL_DIR/.git" && -d "$INSTALL_DIR/backend" && -f "$INSTALL_DIR/backend/.env" ]] || die "checkout Telz invalido"
[[ "$SERVICE_USER" =~ ^[a-z_][a-z0-9_-]{0,31}$ && "$SERVICE_USER" != root ]] || die "usuario de servico invalido"
[[ "$BUILD_USER" =~ ^[a-z_][a-z0-9_-]{0,31}$ && "$BUILD_GROUP" =~ ^[a-z_][a-z0-9_-]{0,31}$ ]] || die "identidade de build invalida"
[[ "$ALEMBIC_TARGET" =~ ^[A-Za-z0-9_]+$ ]] || die "revision Alembic invalida"
id "$SERVICE_USER" >/dev/null 2>&1 || die "usuario de servico inexistente"
command -v python3.12 >/dev/null 2>&1 || die "python3.12 obrigatorio"
command -v pnpm >/dev/null 2>&1 || die "pnpm obrigatorio"
command -v node >/dev/null 2>&1 || die "node obrigatorio"
[[ "$(pnpm --version)" == "10.14.0" ]] || die "pnpm 10.14.0 obrigatorio"
[[ "$(node --version)" == v22.* ]] || die "node 22 obrigatorio"

[[ -z "$(as_service git -C "$INSTALL_DIR" status --porcelain --untracked-files=all)" ]] || die "checkout possui alteracoes ou arquivos nao rastreados"
[[ "$(as_service git -C "$INSTALL_DIR" symbolic-ref --quiet --short HEAD)" == "$BRANCH" ]] || die "checkout deve estar na branch $BRANCH"

active_commit() {
  local active_app
  if [[ -L /var/lib/telz/current ]]; then
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
    as_service git -C "$INSTALL_DIR" rev-parse HEAD
  fi
}

PREVIOUS_COMMIT="$(active_commit)"
[[ "$PREVIOUS_COMMIT" =~ ^[0-9a-f]{40}$ ]] || die "commit ativo invalido"
[[ "$(as_service git -C "$INSTALL_DIR" rev-parse HEAD)" == "$PREVIOUS_COMMIT" ]] || die "checkout fonte diverge da release ativa"

as_service git -C "$INSTALL_DIR" fetch --prune origin "$BRANCH"
REMOTE_COMMIT="$(as_service git -C "$INSTALL_DIR" rev-parse --verify "origin/$BRANCH^{commit}")"
RESOLVED_TARGET="$(as_service git -C "$INSTALL_DIR" rev-parse --verify "$TARGET_COMMIT^{commit}")"
[[ "$RESOLVED_TARGET" == "$TARGET_COMMIT" ]] || die "SHA alvo nao resolveu exatamente"
as_service git -C "$INSTALL_DIR" merge-base --is-ancestor "$PREVIOUS_COMMIT" "$TARGET_COMMIT" || die "alvo nao e fast-forward da release ativa"
as_service git -C "$INSTALL_DIR" merge-base --is-ancestor "$TARGET_COMMIT" "$REMOTE_COMMIT" || die "alvo nao pertence a origin/$BRANCH"

if ! getent group "$BUILD_GROUP" >/dev/null; then groupadd --system "$BUILD_GROUP"; fi
if ! id "$BUILD_USER" >/dev/null 2>&1; then
  useradd --system --gid "$BUILD_GROUP" --home-dir /nonexistent --shell /usr/sbin/nologin --no-create-home "$BUILD_USER"
fi
[[ "$(id -u "$BUILD_USER")" != 0 && "$(id -u "$BUILD_USER")" != "$(id -u "$SERVICE_USER")" ]] || die "UID de build invalido"
[[ "$(id -gn "$BUILD_USER")" == "$BUILD_GROUP" ]] || die "grupo primario de build invalido"
[[ "$(id -nG "$BUILD_USER" | wc -w)" -eq 1 ]] || die "usuario de build possui grupos suplementares"

install -d -m 0755 -o root -g root /var/lib/telz
STAGE_DIR="$(mktemp -d /var/lib/telz/origin-deploy.XXXXXX)"
# The staging root stays owned by root.  The build account can only traverse it
# to its two private child directories below; it cannot list or modify it.
chmod 0711 "$STAGE_DIR"
SOURCE_TARGET="$STAGE_DIR/target-source.tar.gz"
SOURCE_PREVIOUS="$STAGE_DIR/previous-source.tar.gz"
DEPENDENCIES="$STAGE_DIR/dependencies"
OPERATION_BUNDLE="$STAGE_DIR/operation"
mkdir -p "$OPERATION_BUNDLE" "$STAGE_DIR/target-source" "$STAGE_DIR/previous-source"
chown -R root:root "$STAGE_DIR"

BUNDLE_FILES=(
  scripts/update-telz.sh scripts/backup-telz.sh scripts/health-check.sh
  scripts/collect-telz-monitoring.sh scripts/restore-telz.sh scripts/rollback-telz.sh
  scripts/finish-ssl.sh scripts/build-telz-release.sh
  installer/templates/telz-api.service installer/templates/telz-web.service
  installer/templates/telz-whatsapp-gateway.service installer/templates/telz-monitoring.service
  installer/templates/telz-monitoring.timer
)

# `git archive` runs as the service account; root only stores and validates the
# resulting data. Nothing from the target checkout is executed here.
as_service git -C "$INSTALL_DIR" archive "$TARGET_COMMIT" -- "${BUNDLE_FILES[@]}" | tar -xf - -C "$OPERATION_BUNDLE" --no-same-owner --no-same-permissions
mapfile -t ACTUAL_BUNDLE_FILES < <(cd "$OPERATION_BUNDLE" && find . -type f -printf '%P\n' | LC_ALL=C sort)
mapfile -t EXPECTED_BUNDLE_FILES < <(printf '%s\n' "${BUNDLE_FILES[@]}" | LC_ALL=C sort)
[[ "$(printf '%s\n' "${ACTUAL_BUNDLE_FILES[@]}")" == "$(printf '%s\n' "${EXPECTED_BUNDLE_FILES[@]}")" ]] || die "bundle operacional incompleto"
[[ -z "$(find "$OPERATION_BUNDLE" -xdev -type l -print -quit)" ]] || die "bundle operacional contem symlink"
[[ -z "$(find "$OPERATION_BUNDLE" -xdev ! -type d ! -type f -print -quit)" ]] || die "bundle operacional contem tipo especial"
chown -R root:root "$OPERATION_BUNDLE"
find "$OPERATION_BUNDLE" -type d -exec chmod 0555 {} +
find "$OPERATION_BUNDLE/scripts" -type f -exec chmod 0555 {} +
find "$OPERATION_BUNDLE/installer" -type f -exec chmod 0444 {} +
for script in "$OPERATION_BUNDLE"/scripts/*.sh; do bash -n "$script"; done
BUNDLE_UPDATE="$OPERATION_BUNDLE/scripts/update-telz.sh"
require_root_owned_executable "$BUNDLE_UPDATE"

as_service git -C "$INSTALL_DIR" archive --format=tar --add-virtual-file=".telz-source-commit:$TARGET_COMMIT" "$TARGET_COMMIT" | gzip -n > "$SOURCE_TARGET"
as_service git -C "$INSTALL_DIR" archive --format=tar --add-virtual-file=".telz-source-commit:$PREVIOUS_COMMIT" "$PREVIOUS_COMMIT" | gzip -n > "$SOURCE_PREVIOUS"
tar -xzf "$SOURCE_TARGET" -C "$STAGE_DIR/target-source" --no-same-owner --no-same-permissions
tar -xzf "$SOURCE_PREVIOUS" -C "$STAGE_DIR/previous-source" --no-same-owner --no-same-permissions
[[ -f "$STAGE_DIR/target-source/backend/requirements.txt" && -f "$STAGE_DIR/target-source/pnpm-lock.yaml" ]] || die "fonte alvo incompleta"
[[ -f "$STAGE_DIR/previous-source/backend/requirements.txt" && -f "$STAGE_DIR/previous-source/pnpm-lock.yaml" ]] || die "fonte anterior incompleta"
chown -R root:root "$STAGE_DIR/target-source" "$STAGE_DIR/previous-source"
find "$STAGE_DIR/target-source" "$STAGE_DIR/previous-source" -type d -exec chmod 0555 {} +
find "$STAGE_DIR/target-source" "$STAGE_DIR/previous-source" -type f -exec chmod 0444 {} +

install -d -m 0700 -o "$BUILD_USER" -g "$BUILD_GROUP" \
  "$DEPENDENCIES" "$DEPENDENCIES/wheelhouse" "$DEPENDENCIES/pnpm-store" "$STAGE_DIR/build-home"
run_as_builder() {
  sudo -u "$BUILD_USER" -H env HOME="$STAGE_DIR/build-home" PATH=/usr/local/bin:/usr/bin:/bin \
    PIP_DISABLE_PIP_VERSION_CHECK=1 NPM_CONFIG_USERCONFIG=/dev/null "$@"
}
run_as_builder python3.12 -m pip install --dry-run --ignore-installed --only-binary=:all: --report "$DEPENDENCIES/target-report.json" -r "$STAGE_DIR/target-source/backend/requirements.txt"
run_as_builder python3.12 -m pip install --dry-run --ignore-installed --only-binary=:all: --report "$DEPENDENCIES/previous-report.json" -r "$STAGE_DIR/previous-source/backend/requirements.txt"
/usr/bin/python3 - "$DEPENDENCIES/target-report.json" "$STAGE_DIR/target-freeze.txt" "$DEPENDENCIES/previous-report.json" "$STAGE_DIR/previous-freeze.txt" <<'PY'
import json, sys
from pathlib import Path
for report, output in ((sys.argv[1], sys.argv[2]), (sys.argv[3], sys.argv[4])):
    rows = sorted({f"{item['metadata']['name']}=={item['metadata']['version']}" for item in json.loads(Path(report).read_text(encoding='utf-8')).get('install', [])}, key=str.casefold)
    if not rows:
        raise SystemExit('resolver Python nao produziu dependencias')
    Path(output).write_text('\n'.join(rows) + '\n', encoding='utf-8')
PY
chown "$BUILD_USER:$BUILD_GROUP" "$STAGE_DIR"/*-freeze.txt
run_as_builder python3.12 -m pip download --only-binary=:all: --dest "$DEPENDENCIES/wheelhouse" pip==25.1.1 pytest==8.3.5 -r "$STAGE_DIR/target-freeze.txt" -r "$STAGE_DIR/previous-freeze.txt"
run_as_builder pnpm --dir "$STAGE_DIR/target-source" fetch --frozen-lockfile --ignore-scripts --store-dir "$DEPENDENCIES/pnpm-store"
run_as_builder pnpm --dir "$STAGE_DIR/previous-source" fetch --frozen-lockfile --ignore-scripts --store-dir "$DEPENDENCIES/pnpm-store"

/usr/bin/python3 - "$DEPENDENCIES" "$TARGET_COMMIT" "$PREVIOUS_COMMIT" "$STAGE_DIR/target-source" "$STAGE_DIR/previous-source" "$STAGE_DIR/target-freeze.txt" "$STAGE_DIR/previous-freeze.txt" <<'PY'
import hashlib, json, sys
from pathlib import Path
root = Path(sys.argv[1])
digest = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
public = {"VITE_API_URL":"", "VITE_MULTI_TENANT_AUTH_ENABLED":"true", "VITE_PLATFORM_HOSTNAME":"erp.telz.com.br", "VITE_PLATFORM_HOSTNAMES":"erp.telz.com.br"}
public_path = root / '.telz-public-build.json'
public_path.write_text(json.dumps(public, sort_keys=True, separators=(',', ':')) + '\n', encoding='utf-8')
commits = {}
for commit, source, freeze in ((sys.argv[2], sys.argv[4], sys.argv[6]), (sys.argv[3], sys.argv[5], sys.argv[7])):
    commits[commit] = {"python_freeze_sha256": digest(freeze), "requirements_sha256": digest(Path(source) / 'backend' / 'requirements.txt'), "pnpm_lock_sha256": digest(Path(source) / 'pnpm-lock.yaml')}
(root / '.telz-dependencies.json').write_text(json.dumps({"schema_version":1,"target_commit":sys.argv[2],"previous_commit":sys.argv[3],"python":"3.12","pip":"25.1.1","node":"22","pnpm":"10.14.0","public_build_config_sha256":digest(public_path),"commits":commits}, sort_keys=True, separators=(',', ':')) + '\n', encoding='utf-8')
PY
chown -R root:root "$DEPENDENCIES" "$STAGE_DIR/build-home"
find "$DEPENDENCIES" -xdev -type l -print -quit | grep -q . && die "dependencias contem symlink"
find "$DEPENDENCIES" -xdev ! -type d ! -type f -print -quit | grep -q . && die "dependencias contem tipo especial"
find "$DEPENDENCIES" -type d -exec chmod 0555 {} +
find "$DEPENDENCIES" -type f -exec chmod 0444 {} +
DEPENDENCY_ARCHIVE="$STAGE_DIR/dependency-bundle.tar.gz"
tar --dereference --hard-dereference --sort=name --mtime=@0 --owner=0 --group=0 --numeric-owner -C "$DEPENDENCIES" -czf "$DEPENDENCY_ARCHIVE" -- wheelhouse pnpm-store .telz-dependencies.json .telz-public-build.json

for artifact in "$SOURCE_TARGET" "$SOURCE_PREVIOUS" "$DEPENDENCY_ARCHIVE"; do
  require_root_owned_file "$artifact"
done
SOURCE_TARGET_SHA="$(sha256sum "$SOURCE_TARGET" | awk '{print $1}')"
SOURCE_PREVIOUS_SHA="$(sha256sum "$SOURCE_PREVIOUS" | awk '{print $1}')"
DEPENDENCY_SHA="$(sha256sum "$DEPENDENCY_ARCHIVE" | awk '{print $1}')"

env \
  TELZ_SERVICE_USER="$SERVICE_USER" \
  TELZ_EXPECTED_COMMIT="$TARGET_COMMIT" \
  TELZ_PREVIOUS_COMMIT="$PREVIOUS_COMMIT" \
  TELZ_ALEMBIC_TARGET="$ALEMBIC_TARGET" \
  TELZ_OPERATION_BUNDLE_DIR="$OPERATION_BUNDLE" \
  TELZ_SOURCE_ARCHIVE="$SOURCE_TARGET" \
  TELZ_SOURCE_ARCHIVE_SHA256="$SOURCE_TARGET_SHA" \
  TELZ_PREVIOUS_SOURCE_ARCHIVE="$SOURCE_PREVIOUS" \
  TELZ_PREVIOUS_SOURCE_ARCHIVE_SHA256="$SOURCE_PREVIOUS_SHA" \
  TELZ_DEPENDENCY_ARCHIVE="$DEPENDENCY_ARCHIVE" \
  TELZ_DEPENDENCY_ARCHIVE_SHA256="$DEPENDENCY_SHA" \
  TELZ_REQUIRE_PUBLIC_HTTPS=true \
  TELZ_PUBLIC_HEALTH_URL="$PUBLIC_HEALTH_URL" \
  RUN_TESTS=false \
  "$BUNDLE_UPDATE" "$INSTALL_DIR"

ACTIVE_APP="$(readlink -f /var/lib/telz/current)"
[[ "$ACTIVE_APP" == "/var/lib/telz/releases/$TARGET_COMMIT/app" ]] || die "release ativa divergiu do alvo"
/usr/bin/python3 - "$ACTIVE_APP/.telz-release.json" "$TARGET_COMMIT" "$ALEMBIC_TARGET" "$DEPENDENCY_SHA" <<'PY'
import json, sys
from pathlib import Path
data = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
if not (data.get('schema_version') == 2 and data.get('status') == 'validated' and data.get('git_commit') == sys.argv[2] and data.get('alembic_revision') == sys.argv[3] and data.get('dependency_artifact_sha256') == sys.argv[4]):
    raise SystemExit('manifest da release promovida invalido')
PY
echo "[origin-deploy] concluido release=$TARGET_COMMIT revision=$ALEMBIC_TARGET"
