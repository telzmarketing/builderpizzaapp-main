#!/usr/bin/env bash

build_database_url() {
  if [[ "${DATABASE_MODE}" == "external" ]]; then
    validate_required DATABASE_HOST
  else
    DATABASE_HOST="127.0.0.1"
  fi
  export DATABASE_URL="postgresql://${DATABASE_USER}:${DATABASE_PASSWORD}@${DATABASE_HOST}:${DATABASE_PORT}/${DATABASE_NAME}"
}

sql_literal() {
  local value="${1//\'/\'\'}"
  printf "'%s'" "$value"
}

configure_postgresql_local() {
  if [[ "${DATABASE_MODE}" != "local" ]]; then
    info "Banco externo selecionado; pulando criacao local."
    return 0
  fi
  systemctl enable postgresql
  systemctl start postgresql
  sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='${DATABASE_USER}'" | grep -q 1 || \
    sudo -u postgres psql -v ON_ERROR_STOP=1 -c "CREATE USER ${DATABASE_USER} WITH PASSWORD $(sql_literal "$DATABASE_PASSWORD");"
  sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='${DATABASE_NAME}'" | grep -q 1 || \
    sudo -u postgres createdb -O "$DATABASE_USER" "$DATABASE_NAME"
}

run_alembic_gated() {
  [[ "${ALEMBIC_TARGET:-}" =~ ^[A-Za-z0-9_]+$ ]] || {
    fail "ALEMBIC_TARGET obrigatorio e invalido"
    return 1
  }
  info "Revisando Alembic antes de migrations"
  sudo -u "$SERVICE_USER" -H bash -c 'cd "$1" && exec .venv/bin/alembic -c backend/alembic.ini current --verbose' bash "$INSTALL_DIR"
  sudo -u "$SERVICE_USER" -H bash -c 'cd "$1" && exec .venv/bin/alembic -c backend/alembic.ini heads --verbose' bash "$INSTALL_DIR"
  sudo -u "$SERVICE_USER" -H bash -c 'cd "$1" && exec .venv/bin/alembic -c backend/alembic.ini history --verbose' bash "$INSTALL_DIR"

  mapfile -t repository_heads < <(
    sudo -u "$SERVICE_USER" -H bash -c 'cd "$1" && exec .venv/bin/alembic -c backend/alembic.ini heads' bash "$INSTALL_DIR" | awk 'NF {print $1}'
  )
  [[ "${#repository_heads[@]}" -eq 1 ]] || {
    fail "Repositorio deve possuir exatamente um head Alembic"
    return 1
  }
  [[ "${repository_heads[0]}" == "$ALEMBIC_TARGET" ]] || {
    fail "Head ${repository_heads[0]} difere do ALEMBIC_TARGET $ALEMBIC_TARGET"
    return 1
  }

  confirm_or_exit "Executar migration explicita $ALEMBIC_TARGET agora?"
  sudo -u "$SERVICE_USER" -H bash -c 'cd "$1" && exec .venv/bin/alembic -c backend/alembic.ini upgrade "$2"' bash "$INSTALL_DIR" "$ALEMBIC_TARGET"

  mapfile -t database_currents < <(
    sudo -u "$SERVICE_USER" -H bash -c 'cd "$1" && exec .venv/bin/alembic -c backend/alembic.ini current' bash "$INSTALL_DIR" | awk 'NF {print $1}'
  )
  [[ "${#database_currents[@]}" -eq 1 && "${database_currents[0]}" == "$ALEMBIC_TARGET" ]] || {
    fail "Banco nao convergiu para $ALEMBIC_TARGET"
    return 1
  }
  sudo -u "$SERVICE_USER" -H bash -c 'cd "$1" && exec .venv/bin/alembic -c backend/alembic.ini current --verbose' bash "$INSTALL_DIR"
}
