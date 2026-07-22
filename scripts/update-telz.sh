#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

LOCK_FILE="/var/lock/telz-update.lock"
exec 9>"$LOCK_FILE"
flock -n 9 || { echo "Atualizacao Telz ja em execucao." >&2; exit 1; }

BRANCH="${BRANCH:-main}"
RUN_TESTS="${RUN_TESTS:-true}"
CURRENT_COMMIT="$(git rev-parse --short HEAD)"

echo "Commit atual: $CURRENT_COMMIT"
echo "Executando backup antes da atualizacao"
bash scripts/backup-telz.sh

git fetch origin "$BRANCH"
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"

pnpm install --frozen-lockfile
if [[ "$RUN_TESTS" == "true" ]]; then
  pnpm run typecheck
  pnpm test
fi
pnpm run build

if [[ -x .venv/bin/alembic ]]; then
  .venv/bin/alembic -c backend/alembic.ini heads --verbose
  .venv/bin/alembic -c backend/alembic.ini current --verbose || true
  .venv/bin/alembic -c backend/alembic.ini upgrade head
else
  echo "Alembic nao encontrado em .venv; pulando migrations." >&2
fi

systemctl restart telz-api telz-web
if systemctl list-unit-files telz-whatsapp-gateway.service >/dev/null 2>&1; then
  systemctl restart telz-whatsapp-gateway
fi
if ! bash scripts/health-check.sh; then
  echo "Health check falhou. Revertendo codigo para $CURRENT_COMMIT sem downgrade de banco." >&2
  git checkout "$CURRENT_COMMIT"
  pnpm install --frozen-lockfile
  pnpm run build
  systemctl restart telz-api telz-web
  if systemctl list-unit-files telz-whatsapp-gateway.service >/dev/null 2>&1; then
    systemctl restart telz-whatsapp-gateway
  fi
  exit 1
fi

echo "Atualizacao concluida."
