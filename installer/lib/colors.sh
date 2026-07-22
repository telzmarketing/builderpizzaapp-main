#!/usr/bin/env bash

if [[ -t 1 ]]; then
  TELZ_RED=$'\033[31m'
  TELZ_GREEN=$'\033[32m'
  TELZ_YELLOW=$'\033[33m'
  TELZ_BLUE=$'\033[34m'
  TELZ_BOLD=$'\033[1m'
  TELZ_RESET=$'\033[0m'
else
  TELZ_RED=""
  TELZ_GREEN=""
  TELZ_YELLOW=""
  TELZ_BLUE=""
  TELZ_BOLD=""
  TELZ_RESET=""
fi

info() { printf '%s\n' "${TELZ_BLUE}[info]${TELZ_RESET} $*"; }
ok() { printf '%s\n' "${TELZ_GREEN}[ok]${TELZ_RESET} $*"; }
warn() { printf '%s\n' "${TELZ_YELLOW}[aviso]${TELZ_RESET} $*"; }
fail() { printf '%s\n' "${TELZ_RED}[erro]${TELZ_RESET} $*" >&2; }
section() { printf '\n%s\n' "${TELZ_BOLD}== $* ==${TELZ_RESET}"; }
