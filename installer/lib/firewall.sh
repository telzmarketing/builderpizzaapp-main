#!/usr/bin/env bash

configure_firewall() {
  section "Firewall"
  ufw allow OpenSSH
  ufw allow 80/tcp
  ufw allow 443/tcp
  ufw --force enable
  ufw status
}
