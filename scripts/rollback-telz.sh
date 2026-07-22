#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -lt 2 ]]; then
  echo "Uso: sudo bash scripts/rollback-telz.sh /opt/telz COMMIT" >&2
  exit 1
fi

INSTALL_DIR="$1"
TARGET_COMMIT="$2"

if [[ ! -d "$INSTALL_DIR/.git" ]]; then
  echo "[rollback][erro] repositorio nao encontrado" >&2
  exit 1
fi

echo "[rollback] Nao executa downgrade de banco. Apenas codigo/build/services."
read -r -p "Digite ROLLBACK para continuar: " answer
if [[ "$answer" != "ROLLBACK" ]]; then
  echo "[rollback] cancelado"
  exit 1
fi

git -C "$INSTALL_DIR" checkout "$TARGET_COMMIT"
cd "$INSTALL_DIR"
pnpm install --frozen-lockfile
pnpm run build
systemctl restart telz-api telz-web
bash "$INSTALL_DIR/scripts/health-check.sh" "$INSTALL_DIR"
echo "[rollback] concluido"
