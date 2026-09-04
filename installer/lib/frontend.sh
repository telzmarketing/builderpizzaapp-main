#!/usr/bin/env bash

install_node_runtime() {
  local node_major=""
  local nodesource_stage=""
  if command -v node >/dev/null 2>&1; then
    node_major="$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || true)"
  fi
  if [[ "$node_major" != "22" ]]; then
    info "Instalando Node.js 22"
    install -d -m 0755 /etc/apt/keyrings
    install -d -m 0700 -o root -g root /var/lib/telz-installer
    nodesource_stage="$(mktemp -d /var/lib/telz-installer/nodesource.XXXXXX)"
    chmod 0700 "$nodesource_stage"
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key -o "$nodesource_stage/repository.key"
    gpg --batch --yes --dearmor -o "$nodesource_stage/nodesource.gpg" "$nodesource_stage/repository.key"
    printf 'deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_22.x nodistro main\n' > "$nodesource_stage/nodesource.list"
    chmod 0644 "$nodesource_stage/nodesource.gpg" "$nodesource_stage/nodesource.list"
    install -m 0644 -o root -g root "$nodesource_stage/nodesource.gpg" /etc/apt/keyrings/.nodesource.gpg.new
    install -m 0644 -o root -g root "$nodesource_stage/nodesource.list" /etc/apt/sources.list.d/.nodesource.list.new
    mv -T /etc/apt/keyrings/.nodesource.gpg.new /etc/apt/keyrings/nodesource.gpg
    mv -T /etc/apt/sources.list.d/.nodesource.list.new /etc/apt/sources.list.d/nodesource.list
    rm -rf -- "$nodesource_stage"
    apt-get update
    apt-get install -y nodejs
  fi
  [[ "$(node -p 'process.versions.node.split(".")[0]')" == "22" ]] || {
    fail "Node.js 22 e obrigatorio para o frontend"
    return 1
  }
  if ! command -v pnpm >/dev/null 2>&1 || [[ "$(pnpm --version)" != "10.14.0" ]]; then
    npm install -g --ignore-scripts pnpm@10.14.0
  fi
  [[ "$(pnpm --version)" == "10.14.0" ]] || {
    fail "pnpm 10.14.0 e obrigatorio para o frontend"
    return 1
  }
  node -v
  pnpm -v
}

build_frontend() {
  info "Instalando dependencias Node e gerando build"
  sudo -u "$SERVICE_USER" bash -lc "cd '$INSTALL_DIR' && pnpm install --frozen-lockfile"
  sudo -u "$SERVICE_USER" bash -lc "cd '$INSTALL_DIR' && pnpm run typecheck"
  sudo -u "$SERVICE_USER" bash -lc "cd '$INSTALL_DIR' && pnpm test"
  sudo -u "$SERVICE_USER" env \
    VITE_PLATFORM_HOSTNAME="${PLATFORM_DOMAIN}" \
    VITE_MULTI_TENANT_AUTH_ENABLED="${MULTI_TENANT_AUTH_ENABLED:-true}" \
    bash -lc "cd '$INSTALL_DIR' && pnpm run build"
}
