#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${1:-${APP_DIR:-}}"
if [[ -n "$APP_DIR" && -f "$APP_DIR/backend/.env" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$APP_DIR/backend/.env"
  set +a
fi

API_URL="${API_URL:-http://127.0.0.1:${API_PORT:-8000}/health}"
WEB_URL="${WEB_URL:-http://127.0.0.1:${WEB_PORT:-3000}}"

echo "Verificando telz-api"
systemctl is-active telz-api >/dev/null

echo "Verificando telz-web"
systemctl is-active telz-web >/dev/null

if systemctl list-unit-files telz-whatsapp-gateway.service >/dev/null 2>&1; then
  echo "Verificando telz-whatsapp-gateway"
  systemctl is-active telz-whatsapp-gateway >/dev/null
fi

echo "Verificando Nginx"
nginx -t >/dev/null

echo "Verificando API: $API_URL"
curl -fsS "$API_URL" >/dev/null

echo "Verificando Web: $WEB_URL"
curl -fsSI "$WEB_URL" >/dev/null

if command -v pnpm >/dev/null 2>&1 && [[ -n "$APP_DIR" && -f "$APP_DIR/scripts/whatsapp-gateway-health.mjs" ]]; then
  echo "Verificando WhatsApp Gateway runtime"
  pnpm -C "$APP_DIR" whatsapp-gateway:health >/dev/null || echo "WhatsApp Gateway ainda sem sessao online; valide QR Code no painel."
fi

echo "Health check Telz OK"
