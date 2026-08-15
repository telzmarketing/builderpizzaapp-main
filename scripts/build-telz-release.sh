#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

CODE_DIR="${1:?diretorio da release obrigatorio}"
PUBLIC_BUILD_JSON="${2:?configuracao publica obrigatoria}"
RUN_TESTS="${3:-false}"
PYTHON_BOOTSTRAP="${4:-/usr/bin/python3.12}"
DEPENDENCIES_DIR="${5:?diretorio de dependencias obrigatorio}"

[[ "$CODE_DIR" = /* && -d "$CODE_DIR" && ! -L "$CODE_DIR" ]] || {
  echo "[release-build][erro] diretorio de codigo invalido" >&2
  exit 1
}
[[ "$PUBLIC_BUILD_JSON" == "$CODE_DIR/.telz-public-build.json" ]] || {
  echo "[release-build][erro] arquivo de configuracao publica invalido" >&2
  exit 1
}
[[ -f "$PUBLIC_BUILD_JSON" && ! -L "$PUBLIC_BUILD_JSON" ]] || {
  echo "[release-build][erro] configuracao publica ausente" >&2
  exit 1
}
[[ "$RUN_TESTS" == "true" || "$RUN_TESTS" == "false" ]] || {
  echo "[release-build][erro] RUN_TESTS invalido" >&2
  exit 1
}
[[ -x "$PYTHON_BOOTSTRAP" ]] || {
  echo "[release-build][erro] Python 3.12 indisponivel" >&2
  exit 1
}
[[ "$DEPENDENCIES_DIR" = /* && -d "$DEPENDENCIES_DIR/wheelhouse" && -d "$DEPENDENCIES_DIR/pnpm-store" ]] || {
  echo "[release-build][erro] dependencias promovidas invalidas" >&2
  exit 1
}

cd "$CODE_DIR"
"$PYTHON_BOOTSTRAP" -m venv --copies .venv
.venv/bin/python -m pip install --no-index --find-links "$DEPENDENCIES_DIR/wheelhouse" pip==25.1.1 --quiet
.venv/bin/python -m pip install --no-index --find-links "$DEPENDENCIES_DIR/wheelhouse" -r backend/requirements.txt --quiet
.venv/bin/python -m pip check
.venv/bin/python - .telz-python-freeze.txt <<'PY'
import importlib.metadata
import sys

excluded = {"pip", "setuptools", "wheel", "distribute"}
rows = sorted(
    {
        f"{distribution.metadata['Name']}=={distribution.version}"
        for distribution in importlib.metadata.distributions()
        if distribution.metadata.get("Name", "").lower().replace("_", "-") not in excluded
    },
    key=str.casefold,
)
open(sys.argv[1], "w", encoding="utf-8").write("\n".join(rows) + "\n")
PY
pnpm install --offline --frozen-lockfile --silent --package-import-method=copy --store-dir "$DEPENDENCIES_DIR/pnpm-store"
pnpm run typecheck
if [[ "$RUN_TESTS" == "true" ]]; then
  pnpm test
fi

.venv/bin/python - "$PUBLIC_BUILD_JSON" "$CODE_DIR" <<'PY'
import json
import os
import sys
from pathlib import Path

source = Path(sys.argv[1])
code_dir = Path(sys.argv[2])
public = json.loads(source.read_text(encoding="utf-8"))
if not isinstance(public, dict) or any(
    not isinstance(key, str) or not isinstance(value, str)
    for key, value in public.items()
):
    raise SystemExit("configuracao publica invalida")
allowed = {
    "VITE_API_URL",
    "VITE_GOOGLE_CLIENT_ID",
    "VITE_MULTI_TENANT_AUTH_ENABLED",
    "VITE_PLATFORM_HOSTNAME",
    "VITE_PLATFORM_HOSTNAMES",
    "VITE_PUBLIC_EXPERIENCE",
    "VITE_STORE_DOMAIN",
    "VITE_STORE_SCREENSHOT_PROTECTION",
}
if not set(public).issubset(allowed):
    raise SystemExit("configuracao publica contem chave inesperada")
if any("\x00" in value or "\n" in value or "\r" in value for value in public.values()):
    raise SystemExit("configuracao publica contem valor invalido")
environment = {
    "HOME": os.environ.get("HOME", ""),
    "PATH": "/usr/local/bin:/usr/bin:/bin",
    "NODE_ENV": "production",
    **public,
}
os.execvpe("pnpm", ["pnpm", "-C", str(code_dir), "run", "build"], environment)
PY

.venv/bin/python - \
  "$DEPENDENCIES_DIR/.telz-dependencies.json" \
  "$CODE_DIR/.telz-source-commit" \
  "$CODE_DIR/.telz-python-freeze.txt" \
  "$CODE_DIR/backend/requirements.txt" \
  "$CODE_DIR/pnpm-lock.yaml" \
  "$PUBLIC_BUILD_JSON" \
  "$CODE_DIR/.telz-build-metadata.json" \
  "$(.venv/bin/python --version 2>&1)" \
  "$(.venv/bin/python -m pip --version | awk '{print $2}')" \
  "$(node --version)" \
  "$(pnpm --version)" <<'PY'
import hashlib
import json
import re
import sys
from pathlib import Path

dependency_metadata = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
commit = Path(sys.argv[2]).read_text(encoding="ascii").strip()
if not re.fullmatch(r"[0-9a-f]{40}", commit):
    raise SystemExit("marcador do commit invalido")
expected = (dependency_metadata.get("commits") or {}).get(commit)
if not isinstance(expected, dict):
    raise SystemExit("dependencias nao contemplam o commit")

def digest(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

actual = {
    "python_freeze_sha256": digest(sys.argv[3]),
    "requirements_sha256": digest(sys.argv[4]),
    "pnpm_lock_sha256": digest(sys.argv[5]),
}
if actual != expected:
    raise SystemExit("release nao reproduziu as dependencias promovidas")
public_build_config_sha256 = digest(sys.argv[6])
if public_build_config_sha256 != dependency_metadata.get("public_build_config_sha256"):
    raise SystemExit("configuracao publica nao corresponde ao artefato promovido")
toolchain = {
    "python": sys.argv[8],
    "pip": sys.argv[9],
    "node": sys.argv[10],
    "pnpm": sys.argv[11],
}
if not toolchain["python"].startswith("Python 3.12.") or toolchain["pip"] != "25.1.1":
    raise SystemExit("toolchain Python divergiu")
if not toolchain["node"].startswith("v22.") or toolchain["pnpm"] != "10.14.0":
    raise SystemExit("toolchain Node divergiu")
payload = {
    "schema_version": 1,
    "commit": commit,
    **actual,
    "public_build_config_sha256": public_build_config_sha256,
    "toolchain": toolchain,
}
target = Path(sys.argv[7])
target.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY
rm -f -- "$PUBLIC_BUILD_JSON"
find "$CODE_DIR" -xdev -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete
find "$CODE_DIR" -xdev -depth -type d -name __pycache__ -exec rm -rf -- {} +
rm -rf -- \
  "$CODE_DIR/node_modules/.vite" \
  "$CODE_DIR/node_modules/.vite-temp" \
  "$CODE_DIR/node_modules/.cache" \
  "$CODE_DIR/.vite" \
  "$CODE_DIR/.vite-temp" \
  "$CODE_DIR/.cache"
if [[ -f "$CODE_DIR/node_modules/.modules.yaml" ]]; then
  sed -i '/^prunedAt:/d' "$CODE_DIR/node_modules/.modules.yaml"
fi
