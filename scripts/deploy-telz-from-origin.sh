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
ALEMBIC_TARGET="${TELZ_ALEMBIC_TARGET:-20261017_site_config}"
FORWARD_ONLY_CUTOVER="${TELZ_FORWARD_ONLY_CUTOVER:-false}"
FORWARD_ONLY_CUTOVER_CONFIRM="${TELZ_FORWARD_ONLY_CUTOVER_CONFIRM:-}"
LEGACY_ADOPTION="${TELZ_LEGACY_ADOPTION:-false}"
LEGACY_ADOPTION_CONFIRM="${TELZ_LEGACY_ADOPTION_CONFIRM:-}"
LEGACY_ADOPTION_DB_REVISION="${TELZ_LEGACY_ADOPTION_DB_REVISION:-}"
PUBLIC_HEALTH_URL="https://app.telz.com.br/health"

[[ "$TARGET_COMMIT" =~ ^[0-9a-f]{40}$ ]] || die "informe o SHA-1 completo do commit alvo"
[[ "$INSTALL_INPUT" = /* && "$INSTALL_INPUT" != "/" && ! -L "$INSTALL_INPUT" ]] || die "INSTALL_DIR invalido"
INSTALL_DIR="$(realpath -e -- "$INSTALL_INPUT")"
[[ -d "$INSTALL_DIR/.git" && -d "$INSTALL_DIR/backend" && -f "$INSTALL_DIR/backend/.env" ]] || die "checkout Telz invalido"
[[ "$SERVICE_USER" =~ ^[a-z_][a-z0-9_-]{0,31}$ && "$SERVICE_USER" != root ]] || die "usuario de servico invalido"
[[ "$BUILD_USER" =~ ^[a-z_][a-z0-9_-]{0,31}$ && "$BUILD_GROUP" =~ ^[a-z_][a-z0-9_-]{0,31}$ ]] || die "identidade de build invalida"
[[ "$ALEMBIC_TARGET" =~ ^[A-Za-z0-9_]+$ ]] || die "revision Alembic invalida"
[[ "$FORWARD_ONLY_CUTOVER" == "true" || "$FORWARD_ONLY_CUTOVER" == "false" ]] || \
  die "TELZ_FORWARD_ONLY_CUTOVER deve ser true ou false"
[[ "$LEGACY_ADOPTION" == "true" || "$LEGACY_ADOPTION" == "false" ]] || \
  die "TELZ_LEGACY_ADOPTION deve ser true ou false"
[[ -z "$LEGACY_ADOPTION_DB_REVISION" || "$LEGACY_ADOPTION_DB_REVISION" =~ ^[A-Za-z0-9_]+$ ]] || \
  die "TELZ_LEGACY_ADOPTION_DB_REVISION invalida"
if [[ "$FORWARD_ONLY_CUTOVER" == "true" ]]; then
  [[ "$FORWARD_ONLY_CUTOVER_CONFIRM" == "FORWARD_ONLY $TARGET_COMMIT" ]] || \
    die "confirmacao de cutover forward-only invalida para o SHA alvo"
fi
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

LEGACY_RELEASE=false
if [[ ! -e /var/lib/telz/current && ! -L /var/lib/telz/current ]]; then
  LEGACY_RELEASE=true
fi

PREVIOUS_COMMIT="$(active_commit)"
[[ "$PREVIOUS_COMMIT" =~ ^[0-9a-f]{40}$ ]] || die "commit ativo invalido"

if [[ "$LEGACY_ADOPTION" == "true" ]]; then
  [[ "$LEGACY_RELEASE" == "true" ]] || die "adocao legada exige uma release ativa sem current imutavel"
  [[ -n "$LEGACY_ADOPTION_DB_REVISION" ]] || die "adocao legada exige TELZ_LEGACY_ADOPTION_DB_REVISION"
  [[ "$LEGACY_ADOPTION_CONFIRM" == "ADOPT_LEGACY $PREVIOUS_COMMIT $TARGET_COMMIT" ]] || \
    die "confirmacao de adocao legada invalida para os SHAs ativo e alvo"
  [[ "$FORWARD_ONLY_CUTOVER" == "true" && "$FORWARD_ONLY_CUTOVER_CONFIRM" == "FORWARD_ONLY $TARGET_COMMIT" ]] || \
    die "adocao legada exige cutover forward-only explicitamente confirmado"
else
  [[ -z "$LEGACY_ADOPTION_CONFIRM" && -z "$LEGACY_ADOPTION_DB_REVISION" ]] || \
    die "parametros de adocao legada exigem TELZ_LEGACY_ADOPTION=true"
fi

as_service git -C "$INSTALL_DIR" fetch --prune origin "$BRANCH"
REMOTE_COMMIT="$(as_service git -C "$INSTALL_DIR" rev-parse --verify "origin/$BRANCH^{commit}")"
RESOLVED_TARGET="$(as_service git -C "$INSTALL_DIR" rev-parse --verify "$TARGET_COMMIT^{commit}")"
[[ "$RESOLVED_TARGET" == "$TARGET_COMMIT" ]] || die "SHA alvo nao resolveu exatamente"
if [[ "$LEGACY_ADOPTION" == "false" ]]; then
  as_service git -C "$INSTALL_DIR" merge-base --is-ancestor "$PREVIOUS_COMMIT" "$TARGET_COMMIT" || die "alvo nao e fast-forward da release ativa"
fi
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
  scripts/tenant-domain-ssl.py
  scripts/tenant-domain-ssl-renew-hook.py
  installer/templates/telz-domain-ssl.service
  installer/templates/telz-domain-ssl.timer
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

# Keep the archived source immutable.  pnpm may create bookkeeping files next
# to its lockfile even when scripts are disabled, so it receives a separate,
# disposable tree owned by the build account.  Reject link and special-file
# entries before copying and again after copying: the build account must never
# be given a path that can escape this staging directory.
for source_tree in "$STAGE_DIR/target-source" "$STAGE_DIR/previous-source"; do
  [[ -z "$(find "$source_tree" -xdev -type l -print -quit)" ]] || die "fonte arquivada contem symlink"
  [[ -z "$(find "$source_tree" -xdev ! -type d ! -type f -print -quit)" ]] || die "fonte arquivada contem tipo especial"
done

install -d -m 0700 -o "$BUILD_USER" -g "$BUILD_GROUP" \
  "$DEPENDENCIES" "$DEPENDENCIES/wheelhouse" "$DEPENDENCIES/pnpm-store" "$STAGE_DIR/build-home"
install -d -m 0700 -o "$BUILD_USER" -g "$BUILD_GROUP" \
  "$STAGE_DIR/build-home/cache" "$STAGE_DIR/build-home/config"
BUILD_TARGET_SOURCE="$STAGE_DIR/build-target-source"
BUILD_PREVIOUS_SOURCE="$STAGE_DIR/build-previous-source"
install -d -m 0700 -o "$BUILD_USER" -g "$BUILD_GROUP" "$BUILD_TARGET_SOURCE" "$BUILD_PREVIOUS_SOURCE"
cp -a -- "$STAGE_DIR/target-source/." "$BUILD_TARGET_SOURCE/"
cp -a -- "$STAGE_DIR/previous-source/." "$BUILD_PREVIOUS_SOURCE/"
chown -R "$BUILD_USER:$BUILD_GROUP" "$BUILD_TARGET_SOURCE" "$BUILD_PREVIOUS_SOURCE"
for source_tree in "$BUILD_TARGET_SOURCE" "$BUILD_PREVIOUS_SOURCE"; do
  [[ -z "$(find "$source_tree" -xdev -type l -print -quit)" ]] || die "fonte de build contem symlink"
  [[ -z "$(find "$source_tree" -xdev ! -type d ! -type f -print -quit)" ]] || die "fonte de build contem tipo especial"
  find "$source_tree" -type d -exec chmod 0700 {} +
  find "$source_tree" -type f -exec chmod 0600 {} +
done
run_as_builder() {
  sudo -u "$BUILD_USER" -H env -i \
    HOME="$STAGE_DIR/build-home" XDG_CACHE_HOME="$STAGE_DIR/build-home/cache" XDG_CONFIG_HOME="$STAGE_DIR/build-home/config" \
    PATH=/usr/local/bin:/usr/bin:/bin PIP_DISABLE_PIP_VERSION_CHECK=1 \
    NPM_CONFIG_USERCONFIG=/dev/null NPM_CONFIG_GLOBALCONFIG=/dev/null "$@"
}
run_as_builder_in() {
  local working_dir="$1"
  shift
  sudo -u "$BUILD_USER" -H env -i \
    HOME="$STAGE_DIR/build-home" XDG_CACHE_HOME="$STAGE_DIR/build-home/cache" XDG_CONFIG_HOME="$STAGE_DIR/build-home/config" \
    PATH=/usr/local/bin:/usr/bin:/bin PIP_DISABLE_PIP_VERSION_CHECK=1 \
    NPM_CONFIG_USERCONFIG=/dev/null NPM_CONFIG_GLOBALCONFIG=/dev/null \
    /usr/bin/bash -c 'cd -- "$1"; shift; exec "$@"' bash "$working_dir" "$@"
}
prepare_cached_freeze() {
  /usr/bin/python3 -I - "$1" "$2" "$3" <<'PY'
import hashlib, json, os, re, stat, sys
from pathlib import Path

commit, source, output = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
if not re.fullmatch(r'[0-9a-f]{40}', commit):
    raise SystemExit('commit do freeze invalido')
release = Path('/var/lib/telz/releases') / commit
root = release / 'app'
if not release.exists() and not release.is_symlink():
    raise SystemExit(0)  # A genuinely new release resolves from requirements.
def trusted(path, directory=False):
    for candidate in [*reversed(path.parents), path]:
        info = candidate.lstat()
        if stat.S_ISLNK(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise SystemExit('cache do freeze possui caminho inseguro')
        if candidate != path and not stat.S_ISDIR(info.st_mode):
            raise SystemExit('parent do freeze invalido')
    info = path.lstat()
    if not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)):
        raise SystemExit('tipo do cache de freeze invalido')
trusted(root, True)
if (release / '.building').exists() or (release / '.building').is_symlink():
    raise SystemExit('cache de freeze ainda esta em build')
for name in ('.telz-release.json', '.telz-build-metadata.json', '.telz-python-freeze.txt', 'backend/requirements.txt', 'pnpm-lock.yaml'):
    trusted(root / name)
manifest = json.loads((root / '.telz-release.json').read_text())
build = json.loads((root / '.telz-build-metadata.json').read_text())
if (manifest.get('schema_version') != 2 or manifest.get('status') != 'validated'
        or manifest.get('git_commit') != commit or build.get('schema_version') != 1 or build.get('commit') != commit
        or not re.fullmatch(r'[0-9a-f]{64}', str(manifest.get('dependency_artifact_sha256') or ''))):
    raise SystemExit('manifest do freeze invalido')
digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
for key, relative in (('python_freeze_sha256', '.telz-python-freeze.txt'), ('requirements_sha256', 'backend/requirements.txt'), ('pnpm_lock_sha256', 'pnpm-lock.yaml')):
    actual = digest(root / relative)
    if manifest.get(key) != actual or build.get(key) != actual:
        raise SystemExit('digest do freeze cache divergiu')
    if key != 'python_freeze_sha256' and digest(source / relative) != actual:
        raise SystemExit('freeze cache nao corresponde a fonte Git aprovada')
tree = hashlib.sha256()
for candidate in sorted(root.rglob('*'), key=lambda item: item.relative_to(root).as_posix()):
    relative = candidate.relative_to(root).as_posix()
    info = candidate.lstat()
    if info.st_uid != 0 or (not stat.S_ISLNK(info.st_mode) and info.st_mode & 0o022):
        raise SystemExit('conteudo do cache freeze mutavel')
    if relative == '.telz-release.json':
        continue
    if stat.S_ISDIR(info.st_mode):
        kind, data = 'd', b''
    elif stat.S_ISREG(info.st_mode):
        kind, data = 'f', candidate.read_bytes()
    elif stat.S_ISLNK(info.st_mode):
        resolved = candidate.resolve(strict=True)
        try:
            resolved.relative_to(root)
        except ValueError:
            if not (commit == '2f1006860b648cf7a4734222da69879256c174e7' and relative == 'backend/.env'
                    and manifest.get('legacy_compat') == {'backend/.env': '/opt/telz/backend/.env'}
                    and os.readlink(candidate) == '/opt/telz/backend/.env'):
                raise SystemExit('link escapa do cache freeze')
        kind, data = 'l', os.readlink(candidate).encode()
    else:
        raise SystemExit('cache freeze contem tipo especial')
    tree.update(f'{kind}\0{relative}\0{stat.S_IMODE(info.st_mode):04o}\0'.encode())
    tree.update(hashlib.sha256(data).digest())
if tree.hexdigest() != manifest.get('content_sha256'):
    raise SystemExit('conteudo do cache freeze divergiu')
freeze = (root / '.telz-python-freeze.txt').read_bytes()
lines = freeze.decode('utf-8').splitlines()
if not lines or len(freeze) > 262144 or any(not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*==[A-Za-z0-9][A-Za-z0-9.!+_-]*', line) for line in lines):
    raise SystemExit('freeze cache nao contem somente pins de pacote')
names = [re.sub(r'[-_.]+', '-', line.split('==', 1)[0]).lower() for line in lines]
if len(names) != len(set(names)):
    raise SystemExit('freeze cache contem pacote duplicado')
if freeze != ('\n'.join(sorted(set(lines), key=str.casefold)) + '\n').encode():
    raise SystemExit('freeze cache nao e canonico')
output.write_bytes(freeze)  # Data only; never import or execute the cached app.
PY
}
prepare_cached_freeze "$TARGET_COMMIT" "$STAGE_DIR/target-source" "$STAGE_DIR/target-cached-freeze.txt"
prepare_cached_freeze "$PREVIOUS_COMMIT" "$STAGE_DIR/previous-source" "$STAGE_DIR/previous-cached-freeze.txt"
TARGET_CONSTRAINTS=()
PREVIOUS_CONSTRAINTS=()
if [[ -f "$STAGE_DIR/target-cached-freeze.txt" ]]; then
  chmod 0444 "$STAGE_DIR/target-cached-freeze.txt"
  TARGET_CONSTRAINTS=(-c "$STAGE_DIR/target-cached-freeze.txt")
fi
if [[ -f "$STAGE_DIR/previous-cached-freeze.txt" ]]; then
  chmod 0444 "$STAGE_DIR/previous-cached-freeze.txt"
  PREVIOUS_CONSTRAINTS=(-c "$STAGE_DIR/previous-cached-freeze.txt")
fi
run_as_builder python3.12 -m pip install --dry-run --ignore-installed --only-binary=:all: --report "$DEPENDENCIES/target-report.json" -r "$STAGE_DIR/target-source/backend/requirements.txt" "${TARGET_CONSTRAINTS[@]}"
run_as_builder python3.12 -m pip install --dry-run --ignore-installed --only-binary=:all: --report "$DEPENDENCIES/previous-report.json" -r "$STAGE_DIR/previous-source/backend/requirements.txt" "${PREVIOUS_CONSTRAINTS[@]}"
/usr/bin/python3 - "$DEPENDENCIES/target-report.json" "$STAGE_DIR/target-freeze.txt" "$DEPENDENCIES/previous-report.json" "$STAGE_DIR/previous-freeze.txt" "$STAGE_DIR/target-cached-freeze.txt" "$STAGE_DIR/previous-cached-freeze.txt" <<'PY'
import json, sys
from pathlib import Path
for report, output, cached in ((sys.argv[1], sys.argv[2], sys.argv[5]), (sys.argv[3], sys.argv[4], sys.argv[6])):
    rows = sorted({f"{item['metadata']['name']}=={item['metadata']['version']}" for item in json.loads(Path(report).read_text(encoding='utf-8')).get('install', [])}, key=str.casefold)
    if not rows:
        raise SystemExit('resolver Python nao produziu dependencias')
    resolved = ('\n'.join(rows) + '\n').encode('utf-8')
    if Path(cached).exists() and Path(cached).read_bytes() != resolved:
        raise SystemExit('resolver Python divergiu do freeze selado')
    Path(output).write_bytes(resolved)
PY
chmod 0444 "$STAGE_DIR/target-freeze.txt" "$STAGE_DIR/previous-freeze.txt"
if [[ "$TARGET_COMMIT" == "$PREVIOUS_COMMIT" ]]; then
  cmp -s -- "$STAGE_DIR/target-freeze.txt" "$STAGE_DIR/previous-freeze.txt" || die "mesmo commit produziu freezes diferentes"
fi
run_as_builder python3.12 -m pip download --only-binary=:all: --dest "$DEPENDENCIES/wheelhouse" pip==25.1.1 pytest==8.3.5 httpx==0.28.1
run_as_builder python3.12 -m pip download --only-binary=:all: --dest "$DEPENDENCIES/wheelhouse" -r "$STAGE_DIR/target-freeze.txt"
run_as_builder python3.12 -m pip download --only-binary=:all: --dest "$DEPENDENCIES/wheelhouse" -r "$STAGE_DIR/previous-freeze.txt"
run_as_builder_in "$BUILD_TARGET_SOURCE" pnpm fetch --frozen-lockfile --ignore-scripts --store-dir "$DEPENDENCIES/pnpm-store"
run_as_builder_in "$BUILD_PREVIOUS_SOURCE" pnpm fetch --frozen-lockfile --ignore-scripts --store-dir "$DEPENDENCIES/pnpm-store"

/usr/bin/python3 - "$DEPENDENCIES" "$TARGET_COMMIT" "$PREVIOUS_COMMIT" "$STAGE_DIR/target-source" "$STAGE_DIR/previous-source" "$STAGE_DIR/target-freeze.txt" "$STAGE_DIR/previous-freeze.txt" <<'PY'
import hashlib, json, sys
from pathlib import Path
root = Path(sys.argv[1])
digest = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
public = {"VITE_API_URL":"", "VITE_MULTI_TENANT_AUTH_ENABLED":"true", "VITE_PLATFORM_HOSTNAME":"app.telz.com.br", "VITE_PLATFORM_HOSTNAMES":"app.telz.com.br"}
public_path = root / '.telz-public-build.json'
public_path.write_text(json.dumps(public, sort_keys=True, separators=(',', ':')) + '\n', encoding='utf-8')
commits = {}
for commit, source, freeze in ((sys.argv[2], sys.argv[4], sys.argv[6]), (sys.argv[3], sys.argv[5], sys.argv[7])):
    commits[commit] = {"python_freeze_sha256": digest(freeze), "requirements_sha256": digest(Path(source) / 'backend' / 'requirements.txt'), "pnpm_lock_sha256": digest(Path(source) / 'pnpm-lock.yaml')}
(root / '.telz-dependencies.json').write_text(json.dumps({"schema_version":1,"target_commit":sys.argv[2],"previous_commit":sys.argv[3],"python":"3.12","pip":"25.1.1","node":"22","pnpm":"10.14.0","public_build_config_sha256":digest(public_path),"commits":commits}, sort_keys=True, separators=(',', ':')) + '\n', encoding='utf-8')
PY
chown -R root:root "$DEPENDENCIES" "$STAGE_DIR/build-home"
install -d -m 0755 -o root -g root "$DEPENDENCIES/python-freezes"
install -m 0444 -o root -g root "$STAGE_DIR/target-freeze.txt" "$DEPENDENCIES/python-freezes/$TARGET_COMMIT.txt"
install -m 0444 -o root -g root "$STAGE_DIR/previous-freeze.txt" "$DEPENDENCIES/python-freezes/$PREVIOUS_COMMIT.txt"
find "$DEPENDENCIES" -xdev -type l -print -quit | grep -q . && die "dependencias contem symlink"
find "$DEPENDENCIES" -xdev ! -type d ! -type f -print -quit | grep -q . && die "dependencias contem tipo especial"
find "$DEPENDENCIES" -type d -exec chmod 0555 {} +
find "$DEPENDENCIES" -type f -exec chmod 0444 {} +
DEPENDENCY_ARCHIVE="$STAGE_DIR/dependency-bundle.tar.gz"
tar --dereference --hard-dereference --sort=name --mtime=@0 --owner=0 --group=0 --numeric-owner -C "$DEPENDENCIES" -czf "$DEPENDENCY_ARCHIVE" -- wheelhouse pnpm-store python-freezes .telz-dependencies.json .telz-public-build.json

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
  TELZ_FORWARD_ONLY_CUTOVER="$FORWARD_ONLY_CUTOVER" \
  TELZ_FORWARD_ONLY_CUTOVER_CONFIRM="$FORWARD_ONLY_CUTOVER_CONFIRM" \
  TELZ_LEGACY_ADOPTION="$LEGACY_ADOPTION" \
  TELZ_LEGACY_ADOPTION_CONFIRM="$LEGACY_ADOPTION_CONFIRM" \
  TELZ_LEGACY_ADOPTION_DB_REVISION="$LEGACY_ADOPTION_DB_REVISION" \
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
import json, re, sys
from pathlib import Path
data = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
if not (data.get('schema_version') == 2 and data.get('status') == 'validated' and data.get('git_commit') == sys.argv[2] and data.get('alembic_revision') == sys.argv[3] and re.fullmatch(r'[0-9a-f]{64}', str(data.get('dependency_artifact_sha256') or ''))):
    raise SystemExit('manifest da release promovida invalido')
if not re.fullmatch(r'[0-9a-f]{64}', sys.argv[4]):
    raise SystemExit('digest do artefato solicitado invalido')
metadata = json.loads((Path('/var/lib/telz/dependency-bundles') / sys.argv[4] / '.telz-dependencies.json').read_text(encoding='utf-8'))
expected = (metadata.get('commits') or {}).get(sys.argv[2])
keys = {'python_freeze_sha256', 'requirements_sha256', 'pnpm_lock_sha256'}
if not isinstance(expected, dict) or set(expected) != keys or any(data.get(key) != expected[key] for key in keys):
    raise SystemExit('contrato de dependencias da release promovida divergiu')
if data.get('public_build_config_sha256') != metadata.get('public_build_config_sha256'):
    raise SystemExit('configuracao publica da release promovida divergiu')
toolchain = data.get('toolchain') or {}
if (metadata.get('schema_version') != 1 or metadata.get('python') != '3.12'
        or metadata.get('pip') != '25.1.1' or metadata.get('node') != '22' or metadata.get('pnpm') != '10.14.0'
        or not str(toolchain.get('python', '')).startswith('Python 3.12.')
        or toolchain.get('pip') != metadata['pip'] or not str(toolchain.get('node', '')).startswith('v22.')
        or toolchain.get('pnpm') != metadata['pnpm']):
    raise SystemExit('toolchain da release promovida divergiu')
PY
echo "[origin-deploy] concluido release=$TARGET_COMMIT revision=$ALEMBIC_TARGET"
