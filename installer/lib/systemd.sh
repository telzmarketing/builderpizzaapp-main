#!/usr/bin/env bash

install_systemd_units() {
  info "Instalando services systemd"
  mkdir -p "$INSTALL_DIR/.runtime/baileys"
  chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR/.runtime"
  sed \
    -e "s#__INSTALL_DIR__#${INSTALL_DIR}#g" \
    -e "s#__SERVICE_USER__#${SERVICE_USER}#g" \
    -e "s#__API_PORT__#${API_PORT}#g" \
    -e "s#__API_WORKERS__#${API_WORKERS:-2}#g" \
    installer/templates/telz-api.service > /etc/systemd/system/telz-api.service
  sed \
    -e "s#__INSTALL_DIR__#${INSTALL_DIR}#g" \
    -e "s#__SERVICE_USER__#${SERVICE_USER}#g" \
    -e "s#__WEB_PORT__#${WEB_PORT}#g" \
    installer/templates/telz-web.service > /etc/systemd/system/telz-web.service
  if is_true "${INSTALL_WHATSAPP_GATEWAY:-true}"; then
    sed \
      -e "s#__INSTALL_DIR__#${INSTALL_DIR}#g" \
      -e "s#__SERVICE_USER__#${SERVICE_USER}#g" \
      -e "s#__WHATSAPP_GATEWAY_PORT__#${WHATSAPP_GATEWAY_PORT:-3020}#g" \
      installer/templates/telz-whatsapp-gateway.service > /etc/systemd/system/telz-whatsapp-gateway.service
  fi
  systemctl daemon-reload
  systemctl enable telz-api telz-web
  if is_true "${INSTALL_WHATSAPP_GATEWAY:-true}"; then
    systemctl enable telz-whatsapp-gateway
  fi
  systemctl restart telz-api telz-web
  if is_true "${INSTALL_WHATSAPP_GATEWAY:-true}"; then
    systemctl restart telz-whatsapp-gateway
  fi
  systemctl status telz-api --no-pager
  systemctl status telz-web --no-pager
  if is_true "${INSTALL_WHATSAPP_GATEWAY:-true}"; then
    systemctl status telz-whatsapp-gateway --no-pager
  fi
}
