#!/usr/bin/env bash

install_systemd_units() {
  local unit_stage unit_file collector_source health_source api_template web_template gateway_template monitoring_template timer_template
  local -a staged_units
  info "Instalando services systemd"
  mkdir -p "$INSTALL_DIR/.runtime/baileys"
  chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR/.runtime"
  install -d -m 0750 -o "$SERVICE_USER" -g "$SERVICE_USER" "$INSTALL_DIR/uploads"
  collector_source="$(trusted_installer_asset scripts/collect-telz-monitoring.sh)"
  health_source="$(trusted_installer_asset scripts/health-check.sh)"
  api_template="$(trusted_installer_asset installer/templates/telz-api.service)"
  web_template="$(trusted_installer_asset installer/templates/telz-web.service)"
  gateway_template="$(trusted_installer_asset installer/templates/telz-whatsapp-gateway.service)"
  monitoring_template="$(trusted_installer_asset installer/templates/telz-monitoring.service)"
  timer_template="$(trusted_installer_asset installer/templates/telz-monitoring.timer)"
  install -m 0755 -o root -g root "$collector_source" /usr/local/sbin/telz-monitoring-collector
  install -m 0755 -o root -g root "$health_source" /usr/local/sbin/telz-health-check
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
    "$api_template" > "$unit_stage/telz-api.service"
  sed \
    -e "s#__INSTALL_DIR__#${INSTALL_DIR}#g" \
    -e "s#__CODE_DIR__#${INSTALL_DIR}#g" \
    -e "s#__SERVICE_USER__#${SERVICE_USER}#g" \
    -e "s#__WEB_PORT__#${WEB_PORT}#g" \
    "$web_template" > "$unit_stage/telz-web.service"
  if is_true "${INSTALL_WHATSAPP_GATEWAY:-true}"; then
    sed \
      -e "s#__INSTALL_DIR__#${INSTALL_DIR}#g" \
      -e "s#__CODE_DIR__#${INSTALL_DIR}#g" \
      -e "s#__SERVICE_USER__#${SERVICE_USER}#g" \
      -e "s#__WHATSAPP_GATEWAY_PORT__#${WHATSAPP_GATEWAY_PORT:-3020}#g" \
      "$gateway_template" > "$unit_stage/telz-whatsapp-gateway.service"
  fi
  sed \
    -e "s#__INSTALL_DIR__#${INSTALL_DIR}#g" \
    -e "s#__SERVICE_USER__#${SERVICE_USER}#g" \
    -e "s#__API_PORT__#${API_PORT}#g" \
    -e "s#__WEB_PORT__#${WEB_PORT}#g" \
    "$monitoring_template" > "$unit_stage/telz-monitoring.service"
  install -m 0644 -o root -g root "$timer_template" "$unit_stage/telz-monitoring.timer"
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
