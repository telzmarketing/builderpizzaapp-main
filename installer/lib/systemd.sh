#!/usr/bin/env bash

install_systemd_units() {
  local unit_stage unit_file
  local -a staged_units
  info "Instalando services systemd"
  mkdir -p "$INSTALL_DIR/.runtime/baileys"
  chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR/.runtime"
  install -d -m 0750 -o "$SERVICE_USER" -g "$SERVICE_USER" "$INSTALL_DIR/uploads"
  install -m 0755 -o root -g root scripts/collect-telz-monitoring.sh /usr/local/sbin/telz-monitoring-collector
  install -m 0755 -o root -g root scripts/health-check.sh /usr/local/sbin/telz-health-check
  install -d -m 0750 -o root -g "$SERVICE_USER" /var/lib/telz/monitoring
  command -v systemd-analyze >/dev/null 2>&1 || fail "systemd-analyze obrigatorio para validar units"
  unit_stage="$(mktemp -d /tmp/telz-installer-units.XXXXXX)"
  chmod 0700 "$unit_stage"
  sed \
    -e "s#__INSTALL_DIR__#${INSTALL_DIR}#g" \
    -e "s#__CODE_DIR__#${INSTALL_DIR}#g" \
    -e "s#__SERVICE_USER__#${SERVICE_USER}#g" \
    -e "s#__API_PORT__#${API_PORT}#g" \
    -e "s#__API_WORKERS__#${API_WORKERS:-2}#g" \
    installer/templates/telz-api.service > "$unit_stage/telz-api.service"
  sed \
    -e "s#__INSTALL_DIR__#${INSTALL_DIR}#g" \
    -e "s#__CODE_DIR__#${INSTALL_DIR}#g" \
    -e "s#__SERVICE_USER__#${SERVICE_USER}#g" \
    -e "s#__WEB_PORT__#${WEB_PORT}#g" \
    installer/templates/telz-web.service > "$unit_stage/telz-web.service"
  if is_true "${INSTALL_WHATSAPP_GATEWAY:-true}"; then
    sed \
      -e "s#__INSTALL_DIR__#${INSTALL_DIR}#g" \
      -e "s#__CODE_DIR__#${INSTALL_DIR}#g" \
      -e "s#__SERVICE_USER__#${SERVICE_USER}#g" \
      -e "s#__WHATSAPP_GATEWAY_PORT__#${WHATSAPP_GATEWAY_PORT:-3020}#g" \
      installer/templates/telz-whatsapp-gateway.service > "$unit_stage/telz-whatsapp-gateway.service"
  fi
  sed \
    -e "s#__INSTALL_DIR__#${INSTALL_DIR}#g" \
    -e "s#__SERVICE_USER__#${SERVICE_USER}#g" \
    -e "s#__API_PORT__#${API_PORT}#g" \
    -e "s#__WEB_PORT__#${WEB_PORT}#g" \
    installer/templates/telz-monitoring.service > "$unit_stage/telz-monitoring.service"
  install -m 0644 -o root -g root installer/templates/telz-monitoring.timer "$unit_stage/telz-monitoring.timer"
  chmod 0644 "$unit_stage"/*.service
  staged_units=("$unit_stage"/*.service "$unit_stage/telz-monitoring.timer")
  systemd-analyze verify "${staged_units[@]}"
  for unit_file in "${staged_units[@]}"; do
    install -m 0644 -o root -g root "$unit_file" "/etc/systemd/system/$(basename "$unit_file")"
  done
  rm -rf -- "$unit_stage"
  systemctl daemon-reload
  systemctl enable telz-api telz-web telz-monitoring.timer
  if is_true "${INSTALL_WHATSAPP_GATEWAY:-true}"; then
    systemctl enable telz-whatsapp-gateway
  fi
  systemctl restart telz-api telz-web
  if is_true "${INSTALL_WHATSAPP_GATEWAY:-true}"; then
    systemctl restart telz-whatsapp-gateway
  fi
  systemctl start telz-monitoring.timer
  systemctl start telz-monitoring.service
  systemctl status telz-api --no-pager
  systemctl status telz-web --no-pager
  if is_true "${INSTALL_WHATSAPP_GATEWAY:-true}"; then
    systemctl status telz-whatsapp-gateway --no-pager
  fi
  systemctl status telz-monitoring.timer --no-pager
}
