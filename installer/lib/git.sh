#!/usr/bin/env bash

checkout_code() {
  validate_required GIT_REPOSITORY
  validate_required GIT_BRANCH
  if [[ -d "$INSTALL_DIR/.git" ]]; then
    info "Repositorio existente detectado. Atualizando branch $GIT_BRANCH"
    sudo -u "$SERVICE_USER" git -C "$INSTALL_DIR" fetch origin "$GIT_BRANCH"
    sudo -u "$SERVICE_USER" git -C "$INSTALL_DIR" checkout "$GIT_BRANCH"
    sudo -u "$SERVICE_USER" git -C "$INSTALL_DIR" pull --ff-only origin "$GIT_BRANCH"
  else
    if [[ -n "$(find "$INSTALL_DIR" -mindepth 1 -maxdepth 1 2>/dev/null)" ]]; then
      fail "INSTALL_DIR nao esta vazio e nao contem .git: $INSTALL_DIR"
      exit 1
    fi
    sudo -u "$SERVICE_USER" git clone --branch "$GIT_BRANCH" "$GIT_REPOSITORY" "$INSTALL_DIR"
  fi
  sudo -u "$SERVICE_USER" git -C "$INSTALL_DIR" log --oneline -1
}
