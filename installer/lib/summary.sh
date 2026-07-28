#!/usr/bin/env bash

write_summary() {
  section "Resumo final"
  local report="/var/log/telz-installer/last-summary.txt"
  install -d -m 0750 /var/log/telz-installer
  {
    printf 'platform=%s\n' "$PLATFORM_NAME"
    printf 'domain=%s\n' "$PLATFORM_DOMAIN"
    printf 'install_dir=%s\n' "$INSTALL_DIR"
    printf 'admin_email=%s\n' "$ADMIN_EMAIL"
    printf 'admin_name=%s\n' "$ADMIN_NAME"
    printf 'api_service=%s-api\n' "$PLATFORM_SLUG"
    printf 'web_service=%s-web\n' "$PLATFORM_SLUG"
    printf 'multi_tenant_flags=disabled\n'
    printf 'health_local=http://127.0.0.1:%s/health\n' "$API_PORT"
    printf 'health_public=https://%s/health\n' "$PLATFORM_DOMAIN"
  } > "$report"
  cat "$report"
}
