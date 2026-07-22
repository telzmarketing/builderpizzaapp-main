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
  info "Revisando Alembic antes de migrations"
  sudo -u "$SERVICE_USER" bash -lc "cd '$INSTALL_DIR' && source .venv/bin/activate && alembic -c backend/alembic.ini heads --verbose"
  sudo -u "$SERVICE_USER" bash -lc "cd '$INSTALL_DIR' && source .venv/bin/activate && alembic -c backend/alembic.ini current --verbose || true"
  sudo -u "$SERVICE_USER" bash -lc "cd '$INSTALL_DIR' && source .venv/bin/activate && alembic -c backend/alembic.ini history --verbose >/tmp/telz-alembic-history.txt"
  confirm_or_exit "Executar alembic upgrade head agora?"
  sudo -u "$SERVICE_USER" bash -lc "cd '$INSTALL_DIR' && source .venv/bin/activate && alembic -c backend/alembic.ini upgrade head"
  sudo -u "$SERVICE_USER" bash -lc "cd '$INSTALL_DIR' && source .venv/bin/activate && alembic -c backend/alembic.ini current --verbose"
}
