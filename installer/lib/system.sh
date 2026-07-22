#!/usr/bin/env bash

detect_os() {
  if [[ ! -r /etc/os-release ]]; then
    fail "Nao foi possivel detectar o sistema operacional."
    exit 1
  fi
  . /etc/os-release
  if [[ "${ID:-}" != "ubuntu" ]]; then
    fail "Sistema nao suportado nesta versao: ${PRETTY_NAME:-desconhecido}. Use Ubuntu 22.04/24.04."
    exit 1
  fi
  case "${VERSION_ID:-}" in
    22.04|24.04) ok "Ubuntu suportado: ${VERSION_ID}" ;;
    *) warn "Ubuntu ${VERSION_ID:-desconhecido}; suporte principal esperado: 22.04/24.04." ;;
  esac
}

install_system_packages() {
  info "Instalando pacotes base"
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y \
    ca-certificates curl wget git unzip build-essential software-properties-common \
    gnupg ufw nginx python3 python3-venv python3-dev python3-pip postgresql postgresql-contrib
}

ensure_service_user() {
  if id "$SERVICE_USER" >/dev/null 2>&1; then
    ok "Usuario existente: $SERVICE_USER"
  else
    adduser --disabled-password --gecos "" "$SERVICE_USER"
    ok "Usuario criado: $SERVICE_USER"
  fi
}

prepare_directories() {
  validate_install_dir "$INSTALL_DIR"
  mkdir -p "$INSTALL_DIR" /var/log/telz-installer /var/lib/telz-installer/state /var/backups/telz
  chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR" /var/backups/telz
  chmod 750 "$INSTALL_DIR"
}
