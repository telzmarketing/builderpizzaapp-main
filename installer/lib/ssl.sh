#!/usr/bin/env bash

install_ssl_if_requested() {
  local ssl_helper="/usr/local/sbin/telz-finish-ssl"
  local ssl_source
  ssl_source="$(trusted_installer_asset scripts/finish-ssl.sh)"
  install -m 0755 -o root -g root "$ssl_source" "$ssl_helper"
  if ! is_true "$INSTALL_SSL"; then
    info "SSL desabilitado na configuracao. Helper seguro instalado em $ssl_helper."
    return 0
  fi
  validate_required PLATFORM_DOMAIN
  validate_required SSL_EMAIL
  warn "SSL requer DNS apontando para esta VPS."
  "$ssl_helper" "$PLATFORM_DOMAIN" "$SSL_EMAIL" || \
    warn "SSL nao concluido. Finalize depois com: sudo $ssl_helper ${PLATFORM_DOMAIN} ${SSL_EMAIL}"
}
