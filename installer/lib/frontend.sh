#!/usr/bin/env bash

install_node_runtime() {
  if ! command -v node >/dev/null 2>&1; then
    info "Instalando Node.js 22"
    install -d -m 0755 /etc/apt/keyrings
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key -o /tmp/nodesource-repo.gpg.key
    gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg /tmp/nodesource-repo.gpg.key
    chmod 0644 /etc/apt/keyrings/nodesource.gpg
    printf 'deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_22.x nodistro main\n' > /etc/apt/sources.list.d/nodesource.list
    apt-get update
    apt-get install -y nodejs
  fi
  if ! command -v pnpm >/dev/null 2>&1; then
    npm install -g pnpm
  fi
  node -v
  pnpm -v
}

build_frontend() {
  info "Instalando dependencias Node e gerando build"
  sudo -u "$SERVICE_USER" bash -lc "cd '$INSTALL_DIR' && pnpm install --frozen-lockfile"
  sudo -u "$SERVICE_USER" bash -lc "cd '$INSTALL_DIR' && pnpm run typecheck"
  sudo -u "$SERVICE_USER" bash -lc "cd '$INSTALL_DIR' && pnpm test"
  sudo -u "$SERVICE_USER" bash -lc "cd '$INSTALL_DIR' && pnpm run build"
}
