#!/usr/bin/env bash
set -Eeuo pipefail

DOMAIN="${1:-}"
EMAIL="${2:-}"

if [[ -z "$DOMAIN" || -z "$EMAIL" ]]; then
  echo "Uso: sudo bash scripts/finish-ssl.sh app.seudominio.com.br admin@seudominio.com.br" >&2
  exit 1
fi

if ! command -v certbot >/dev/null 2>&1; then
  apt-get update
  apt-get install -y certbot python3-certbot-nginx
fi

nginx -t
certbot --nginx -d "$DOMAIN" --email "$EMAIL" --agree-tos --non-interactive --redirect
systemctl reload nginx
echo "[ssl] concluido para $DOMAIN"
