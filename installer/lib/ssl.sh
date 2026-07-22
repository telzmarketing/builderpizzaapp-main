#!/usr/bin/env bash

install_ssl_if_requested() {
  if ! is_true "$INSTALL_SSL"; then
    info "SSL desabilitado na configuracao."
    return 0
  fi
  validate_required PLATFORM_DOMAIN
  validate_required SSL_EMAIL
  if ! command -v certbot >/dev/null 2>&1; then
    apt-get install -y certbot python3-certbot-nginx
  fi
  warn "SSL requer DNS apontando para esta VPS. Se falhar, execute scripts/finish-ssl.sh depois."
  certbot --nginx -d "$PLATFORM_DOMAIN" --email "$SSL_EMAIL" --agree-tos --non-interactive --redirect || \
    warn "SSL nao concluido. Finalize depois com: sudo bash scripts/finish-ssl.sh ${PLATFORM_DOMAIN} ${SSL_EMAIL}"
}
