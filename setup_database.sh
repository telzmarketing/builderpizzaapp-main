#!/usr/bin/env bash
# =============================================================================
# setup_database.sh — Cria o banco de dados PostgreSQL da aplicação
# =============================================================================
#
# Uso:
#   bash setup_database.sh --nome minhaloja
#   bash setup_database.sh --nome brasell --usuario brasell_user --senha M1nh@Senha
#   bash setup_database.sh --nome brasell --pg-usuario postgres --pg-host localhost
#
# Parâmetros:
#   --nome        Nome do banco de dados e da loja (obrigatório)
#                 Exemplos: brasell | pizzariajoia | lanchonete
#   --usuario     Usuário PostgreSQL que a aplicação usará
#                 Padrão: <nome>_user
#   --senha       Senha do usuário da aplicação
#                 Padrão: gerada automaticamente
#   --pg-usuario  Superusuário do PostgreSQL para executar o script
#                 Padrão: postgres
#   --pg-host     Host do PostgreSQL
#                 Padrão: localhost
#   --pg-porta    Porta do PostgreSQL
#                 Padrão: 5432
# =============================================================================

set -euo pipefail

# ── Cores para output ─────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'

info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[AVISO]${NC} $*"; }
error()   { echo -e "${RED}[ERRO]${NC}  $*" >&2; exit 1; }

# ── Valores padrão ────────────────────────────────────────────────────────────
DB_NAME=""
DB_USER=""
DB_PASS=""
PG_USER="postgres"
PG_HOST="localhost"
PG_PORT="5432"

# ── Parse dos argumentos ──────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --nome)       DB_NAME="$2";   shift 2 ;;
    --usuario)    DB_USER="$2";   shift 2 ;;
    --senha)      DB_PASS="$2";   shift 2 ;;
    --pg-usuario) PG_USER="$2";   shift 2 ;;
    --pg-host)    PG_HOST="$2";   shift 2 ;;
    --pg-porta)   PG_PORT="$2";   shift 2 ;;
    -h|--help)
      sed -n '2,30p' "$0" | grep '^#' | sed 's/^# \?//'
      exit 0
      ;;
    *)
      error "Argumento desconhecido: $1. Use --help para ajuda."
      ;;
  esac
done

# ── Validações ────────────────────────────────────────────────────────────────
[[ -z "$DB_NAME" ]] && error "O parâmetro --nome é obrigatório.\nExemplo: bash setup_database.sh --nome minhaloja"

# Nome só pode ter letras minúsculas, números e underscores
if [[ ! "$DB_NAME" =~ ^[a-z][a-z0-9_]*$ ]]; then
  error "Nome inválido: '$DB_NAME'\nUse apenas letras minúsculas, números e _ (sem espaços, sem maiúsculas, sem hífens).\nExemplo: minhaloja | brasell | pizzaria_joao"
fi

[[ -z "$DB_USER" ]] && DB_USER="${DB_NAME}_user"
[[ -z "$DB_PASS" ]] && DB_PASS="$(openssl rand -base64 18 | tr -d '/+' | head -c 24)"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SQL_FILE="$SCRIPT_DIR/setup_database.sql"

[[ ! -f "$SQL_FILE" ]] && error "Arquivo setup_database.sql não encontrado em: $SCRIPT_DIR"

# ── Resumo antes de executar ──────────────────────────────────────────────────
echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║        Configuração do Banco de Dados            ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BOLD}Nome do banco:${NC}    $DB_NAME"
echo -e "  ${BOLD}Usuário da app:${NC}   $DB_USER"
echo -e "  ${BOLD}Senha da app:${NC}     $DB_PASS"
echo -e "  ${BOLD}PG superusuário:${NC}  $PG_USER @ $PG_HOST:$PG_PORT"
echo ""

read -rp "Confirmar e executar? [s/N] " CONFIRM
[[ ! "$CONFIRM" =~ ^[sS]$ ]] && { warn "Cancelado."; exit 0; }
echo ""

PSQL_CMD="psql -U $PG_USER -h $PG_HOST -p $PG_PORT"

# ── 1. Cria o usuário da aplicação se não existir ─────────────────────────────
info "Criando usuário PostgreSQL '$DB_USER'..."
$PSQL_CMD -d postgres -c \
  "DO \$\$ BEGIN
     IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '$DB_USER') THEN
       CREATE USER \"$DB_USER\" WITH PASSWORD '$DB_PASS';
     ELSE
       ALTER USER \"$DB_USER\" WITH PASSWORD '$DB_PASS';
     END IF;
   END \$\$;" \
  && success "Usuário '$DB_USER' pronto." \
  || error "Falha ao criar usuário."

# ── 2. Executa o script SQL com as variáveis ──────────────────────────────────
info "Executando setup_database.sql no banco '$DB_NAME'..."
$PSQL_CMD -d postgres \
  -v DBNAME="$DB_NAME" \
  -v DBUSER="$DB_USER" \
  --set=ON_ERROR_STOP=1 \
  -f "$SQL_FILE" \
  && success "Tabelas, índices e dados iniciais criados." \
  || error "Falha ao executar o script SQL."

# ── 3. Concede permissões ao usuário da aplicação ─────────────────────────────
info "Concedendo permissões ao usuário '$DB_USER' no banco '$DB_NAME'..."
$PSQL_CMD -d "$DB_NAME" -c \
  "GRANT ALL PRIVILEGES ON DATABASE \"$DB_NAME\" TO \"$DB_USER\";
   GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO \"$DB_USER\";
   GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO \"$DB_USER\";
   GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO \"$DB_USER\";
   ALTER DEFAULT PRIVILEGES IN SCHEMA public
     GRANT ALL ON TABLES TO \"$DB_USER\";
   ALTER DEFAULT PRIVILEGES IN SCHEMA public
     GRANT ALL ON SEQUENCES TO \"$DB_USER\";" \
  && success "Permissões concedidas." \
  || error "Falha ao conceder permissões."

# ── 4. Salva as informações de conexão ────────────────────────────────────────
CONN_FILE="$SCRIPT_DIR/db_connection.txt"
cat > "$CONN_FILE" << EOF
# Informações de conexão geradas em $(date '+%Y-%m-%d %H:%M:%S')
# GUARDE ESTE ARQUIVO COM SEGURANÇA — não commite no git!

DB_NAME=$DB_NAME
DB_USER=$DB_USER
DB_PASS=$DB_PASS
DB_HOST=$PG_HOST
DB_PORT=$PG_PORT

# Cole no backend/.env:
DATABASE_URL=postgresql://${DB_USER}:${DB_PASS}@${PG_HOST}:${PG_PORT}/${DB_NAME}
EOF
chmod 600 "$CONN_FILE"

# ── Resumo final ──────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}${BOLD}║  Banco de dados configurado com sucesso!                     ║${NC}"
echo -e "${GREEN}${BOLD}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BOLD}Banco:${NC}           $DB_NAME"
echo -e "  ${BOLD}DATABASE_URL:${NC}    postgresql://${DB_USER}:${DB_PASS}@${PG_HOST}:${PG_PORT}/${DB_NAME}"
echo ""
echo -e "  ${BOLD}Próximo passo — cole no backend/.env:${NC}"
echo -e "  ${YELLOW}DATABASE_URL=postgresql://${DB_USER}:${DB_PASS}@${PG_HOST}:${PG_PORT}/${DB_NAME}${NC}"
echo ""
echo -e "  Informações salvas em: ${BOLD}db_connection.txt${NC}"
echo ""
