#!/usr/bin/env bash

load_env_file() {
  local file="$1"
  [[ -f "$file" ]] || return 0
  set -a
  # shellcheck disable=SC1090
  source "$file"
  set +a
}

ask() {
  local var="$1"
  local label="$2"
  local default="${3:-}"
  local secret="${4:-false}"
  local answer

  if [[ "${TELZ_NON_INTERACTIVE:-false}" == "true" ]]; then
    return 0
  fi

  if [[ "$secret" == "true" ]]; then
    read -r -s -p "$label${default:+ [$default]}: " answer
    printf '\n'
  else
    read -r -p "$label${default:+ [$default]}: " answer
  fi

  if [[ -z "$answer" ]]; then
    answer="$default"
  fi
  printf -v "$var" '%s' "$answer"
}

ask_required() {
  local var="$1"
  local label="$2"
  local default="${3:-}"
  local secret="${4:-false}"
  while true; do
    ask "$var" "$label" "$default" "$secret"
    if [[ -n "${!var:-}" ]]; then
      break
    fi
    warn "Valor obrigatorio."
  done
}

ask_yes_no() {
  local var="$1"
  local label="$2"
  local default="${3:-false}"
  local answer
  if [[ "${TELZ_NON_INTERACTIVE:-false}" == "true" ]]; then
    return 0
  fi
  read -r -p "$label [$default]: " answer
  answer="${answer:-$default}"
  case "${answer,,}" in
    y|yes|s|sim|true|1) printf -v "$var" 'true' ;;
    *) printf -v "$var" 'false' ;;
  esac
}

collect_answers() {
  section "Perguntas da instalacao"
  ask_required PLATFORM_NAME "Nome da plataforma" "${PLATFORM_NAME:-Telz}"
  ask_required PLATFORM_SLUG "Slug dos servicos" "${PLATFORM_SLUG:-telz}"
  ask_required PLATFORM_DOMAIN "Dominio principal sem https" "${PLATFORM_DOMAIN:-}"
  ask ADMIN_EMAIL "Email admin inicial" "${ADMIN_EMAIL:-}"
  ask SSL_EMAIL "Email para SSL" "${SSL_EMAIL:-${ADMIN_EMAIL:-}}"
  ask_required INSTALL_DIR "Diretorio de instalacao" "${INSTALL_DIR:-/opt/telz}"
  ask_required SERVICE_USER "Usuario Linux do servico" "${SERVICE_USER:-telz}"
  ask_required GIT_REPOSITORY "Repositorio Git" "${GIT_REPOSITORY:-}"
  ask_required GIT_BRANCH "Branch" "${GIT_BRANCH:-main}"
  ask_required DATABASE_NAME "Nome do banco" "${DATABASE_NAME:-telz}"
  ask_required DATABASE_USER "Usuario do banco" "${DATABASE_USER:-telz_user}"
  ask_required DATABASE_PASSWORD "Senha do banco" "${DATABASE_PASSWORD:-}" true
  ask_required JWT_SECRET_KEY "JWT_SECRET_KEY" "${JWT_SECRET_KEY:-}" true
  ask PAYMENT_PROVIDER "Provider inicial de pagamento" "${PAYMENT_PROVIDER:-mock}"
  ask PAYMENT_GATEWAY "Gateway inicial de pagamento" "${PAYMENT_GATEWAY:-mock}"
  ask MERCADO_PAGO_PUBLIC_KEY "Mercado Pago Public Key opcional" "${MERCADO_PAGO_PUBLIC_KEY:-}"
  ask MERCADO_PAGO_ACCESS_TOKEN "Mercado Pago Access Token opcional" "${MERCADO_PAGO_ACCESS_TOKEN:-}" true
  ask MERCADO_PAGO_WEBHOOK_SECRET "Mercado Pago Webhook Secret opcional" "${MERCADO_PAGO_WEBHOOK_SECRET:-}" true
  ask ASAAS_API_KEY "ASAAS API Key opcional" "${ASAAS_API_KEY:-}" true
  ask ASAAS_WEBHOOK_TOKEN "ASAAS Webhook Token opcional" "${ASAAS_WEBHOOK_TOKEN:-}" true
  ask_yes_no INSTALL_NGINX "Configurar Nginx" "${INSTALL_NGINX:-true}"
  ask_yes_no INSTALL_SSL "Configurar SSL agora" "${INSTALL_SSL:-false}"
  ask_yes_no INSTALL_BACKUP "Criar backup inicial" "${INSTALL_BACKUP:-true}"
  ask_yes_no INSTALL_WHATSAPP_GATEWAY "Instalar WhatsApp Gateway junto com o sistema" "${INSTALL_WHATSAPP_GATEWAY:-true}"
}

confirm_plan() {
  section "Resumo antes de alterar a VPS"
  for key in PLATFORM_NAME PLATFORM_SLUG PLATFORM_DOMAIN INSTALL_DIR SERVICE_USER GIT_REPOSITORY GIT_BRANCH DATABASE_MODE DATABASE_HOST DATABASE_NAME DATABASE_USER API_PORT WEB_PORT PAYMENT_PROVIDER PAYMENT_GATEWAY MERCADO_PAGO_PUBLIC_KEY MERCADO_PAGO_ACCESS_TOKEN MERCADO_PAGO_WEBHOOK_SECRET ASAAS_API_KEY ASAAS_WEBHOOK_TOKEN INSTALL_NGINX INSTALL_SSL INSTALL_BACKUP INSTALL_WHATSAPP_GATEWAY; do
    printf '%s=%s\n' "$key" "$(mask_value "$key" "${!key:-}")"
  done
  if [[ "${TELZ_NON_INTERACTIVE:-false}" == "true" || "${TELZ_ASSUME_YES:-false}" == "true" ]]; then
    return 0
  fi
  local answer
  read -r -p "Continuar? Digite SIM para confirmar: " answer
  [[ "$answer" == "SIM" ]] || {
    fail "Instalacao cancelada pelo operador."
    exit 1
  }
}

confirm_or_exit() {
  local message="$1"
  if [[ "${TELZ_NON_INTERACTIVE:-false}" == "true" || "${TELZ_ASSUME_YES:-false}" == "true" ]]; then
    return 0
  fi
  local answer
  read -r -p "$message Digite SIM para confirmar: " answer
  [[ "$answer" == "SIM" ]] || {
    fail "Operacao cancelada pelo operador."
    exit 1
  }
}
