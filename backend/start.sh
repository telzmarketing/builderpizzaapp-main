#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# Script de inicialização do backend PizzaApp
# Uso: bash backend/start.sh
# ──────────────────────────────────────────────────────────────
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "📦 Instalando dependências..."
pip install -r backend/requirements.txt

echo "🚀 Iniciando servidor FastAPI na porta 8000..."
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
