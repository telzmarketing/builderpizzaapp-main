#!/usr/bin/env bash

install_nginx_site() {
  local nginx_template
  if ! is_true "$INSTALL_NGINX"; then
    info "Nginx desabilitado na configuracao."
    return 0
  fi
  validate_required PLATFORM_DOMAIN
  info "Configurando Nginx"
  nginx_template="$(trusted_installer_asset installer/templates/nginx-telz.conf)"
  sed \
    -e "s#__PLATFORM_DOMAIN__#${PLATFORM_DOMAIN}#g" \
    -e "s#__API_PORT__#${API_PORT}#g" \
    -e "s#__WEB_PORT__#${WEB_PORT}#g" \
    "$nginx_template" > /etc/nginx/sites-available/telz.conf
  ln -sfn /etc/nginx/sites-available/telz.conf /etc/nginx/sites-enabled/telz.conf
  nginx -t
  systemctl reload nginx
}
