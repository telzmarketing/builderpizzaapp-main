#!/usr/bin/env bash

configure_firewall() {
  local sshd_effective connection_port port
  local -a ssh_ports=()
  section "Firewall"
  require_command sshd
  if ! sshd_effective="$(sshd -T 2>/dev/null)"; then
    fail "Nao foi possivel determinar as portas efetivas do SSH; UFW nao sera habilitado"
    return 1
  fi
  while read -r port; do
    validate_port "$port" && ssh_ports+=("$port")
  done < <(awk '$1 == "port" {print $2}' <<< "$sshd_effective")
  if [[ -n "${SSH_CONNECTION:-}" ]]; then
    read -r -a ssh_connection_fields <<< "$SSH_CONNECTION"
    connection_port="${ssh_connection_fields[3]:-}"
    validate_port "$connection_port" && ssh_ports+=("$connection_port")
  fi
  mapfile -t ssh_ports < <(printf '%s\n' "${ssh_ports[@]}" | awk 'NF && !seen[$0]++')
  [[ "${#ssh_ports[@]}" -gt 0 ]] || {
    fail "Nenhuma porta SSH efetiva foi detectada; UFW nao sera habilitado"
    return 1
  }
  for port in "${ssh_ports[@]}"; do
    info "Permitindo SSH na porta efetiva $port/tcp"
    ufw allow "${port}/tcp"
  done
  ufw allow 80/tcp
  ufw allow 443/tcp
  ufw --force enable
  ufw status
}
