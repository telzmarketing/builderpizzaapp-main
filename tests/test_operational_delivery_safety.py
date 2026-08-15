from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_monitoring_lock_is_writable_under_strict_systemd_sandbox():
    collector = read("scripts/collect-telz-monitoring.sh")
    unit = read("installer/templates/telz-monitoring.service")

    assert 'LOCK_DIR="${TELZ_MONITORING_LOCK_DIR:-/run/telz-monitoring}"' in collector
    assert 'exec 9>"$LOCK_DIR/collector.lock"' in collector
    assert "/run/lock/telz-monitoring.lock" not in collector
    assert "RuntimeDirectory=telz-monitoring" in unit
    assert "RuntimeDirectoryMode=0750" in unit
    assert "ProtectSystem=strict" in unit


def test_collector_rejects_symlink_roots_before_recursive_metrics():
    collector = read("scripts/collect-telz-monitoring.sh")

    assert "if path.is_symlink() or not path.is_dir():" in collector
    assert "uploads_safe = uploads_root.is_dir() and not uploads_root.is_symlink()" in collector
    assert "if uploads_safe and tenant_root.is_dir() and not tenant_root.is_symlink():" in collector


def test_updater_arms_release_recovery_before_mutation():
    updater = read("scripts/update-telz.sh")

    assert "RECOVERY_REQUIRED=true" in updater
    assert updater.rindex("RECOVERY_REQUIRED=true") < updater.rindex("\nquiesce_services\n")
    assert 'trap \'rc=$?; on_error "$rc"\' ERR' in updater
    assert "activate_release" in updater
    assert "restore_previous_release" in updater


def test_updater_transactions_root_owned_helpers_and_validated_units():
    updater = read("scripts/update-telz.sh")

    assert "snapshot_operational_artifacts" in updater
    assert "restore_operational_artifacts" in updater
    assert 'install -m 0755 -o root -g root "$BUNDLE_RESTORE" "$RESTORE_COMMAND"' in updater
    assert 'install -m 0755 -o root -g root "$BUNDLE_SSL" "$SSL_COMMAND"' in updater
    assert updater.index("systemd-analyze verify") < updater.index(
        'install -m 0644 -o root -g root "$unit_file"'
    )
    assert updater.index('"$HEALTH_COMMAND" "$INSTALL_DIR"') < updater.rindex(
        "OPERATIONS_CHANGED=false"
    )


def test_rollback_requires_full_sha_and_only_swaps_validated_release():
    rollback = read("scripts/rollback-telz.sh")

    assert '[[ "$REQUESTED_COMMIT" =~ ^[0-9a-f]{40}$ ]]' in rollback
    assert 'TARGET_CODE_DIR="$(validate_release_path "$RELEASES_DIR/$REQUESTED_COMMIT/app")"' in rollback
    assert 'mv -Tf -- "$temporary" "$CURRENT_LINK"' in rollback
    assert "schema_pair_is_compatible" in rollback
    assert "git checkout" not in rollback
    assert "pip install" not in rollback
    assert "pnpm install" not in rollback
    assert 'pnpm -C "$INSTALL_DIR"' not in rollback
    assert 'bash "$INSTALL_DIR/scripts/backup-telz.sh"' not in rollback
    assert 'bash "$INSTALL_DIR/scripts/health-check.sh"' not in rollback


def test_restore_uses_write_ahead_flags_and_cleans_staging_directory():
    restore = read("scripts/restore-telz.sh")

    assert restore.index("UPLOADS_OLD_MOVED=true") < restore.index(
        'mv -- "$INSTALL_DIR/uploads" "$ROLLBACK_DIR/uploads"'
    )
    assert restore.index("UPLOADS_NEW_INSTALLED=true") < restore.index(
        'mv -- "$STAGE_DIR/uploads" "$INSTALL_DIR/uploads"'
    )
    assert restore.index("BAILEYS_OLD_MOVED=true") < restore.index(
        'mv -- "$INSTALL_DIR/.runtime/baileys" "$ROLLBACK_DIR/baileys"'
    )
    assert restore.index("BAILEYS_NEW_INSTALLED=true") < restore.index(
        'mv -- "$STAGE_DIR/.runtime/baileys" "$INSTALL_DIR/.runtime/baileys"'
    )
    assert "cleanup_restore_stage" in restore
    assert 'trap \'restore_previous_state 143\' TERM HUP' in restore
    assert 'TELZ_ALEMBIC_TARGET="$MANIFEST_REVISION"' in restore
    assert "member.isdir() or member.isreg()" in restore
    assert "member.issym()" not in restore


def test_installer_verifies_units_before_install_and_gates_requested_https():
    systemd = read("installer/lib/systemd.sh")
    installer = read("installer/install.sh")

    assert systemd.index("systemd-analyze verify") < systemd.index(
        '"/etc/systemd/system/$(basename "$unit_file")"'
    )
    assert 'install -m 0644 -o root -g root "$unit_file"' in systemd
    assert 'if is_true "$INSTALL_SSL"; then' in installer
    assert 'TELZ_REQUIRE_PUBLIC_HTTPS="$REQUIRE_PUBLIC_HTTPS"' in installer
    assert '|| warn "Health check falhou' not in installer


def test_public_health_gate_requires_https_certificate_and_valid_json():
    health = read("scripts/health-check.sh")
    updater = read("scripts/update-telz.sh")

    assert 'REQUIRE_PUBLIC_HTTPS="${TELZ_REQUIRE_PUBLIC_HTTPS:-true}"' in updater
    assert "parsed.scheme.lower() != \"https\"" in health
    assert "parsed.path.rstrip(\"/\") != \"/health\"" in health
    assert "curl --proto '=https' --tlsv1.2" in health
    assert 'validate_health_response "$PUBLIC_RESPONSE"' in health
    assert "erp.telz.com.br" not in health


def test_ssl_followup_is_installed_and_documented_as_root_owned_helper():
    installer_ssl = read("installer/lib/ssl.sh")
    install_doc = read("docs/INSTALL_TELZ_VPS.md")

    assert 'install -m 0755 -o root -g root scripts/finish-ssl.sh "$ssl_helper"' in installer_ssl
    assert '"$ssl_helper" "$PLATFORM_DOMAIN" "$SSL_EMAIL"' in installer_ssl
    assert "sudo bash scripts/finish-ssl.sh" not in install_doc
    assert "sudo /usr/local/sbin/telz-finish-ssl" in install_doc


def test_ci_validates_on_push_and_deploys_only_by_manual_dispatch():
    workflow = read(".github/workflows/deploy.yml")

    assert "Validar scripts Bash" in workflow
    assert "bash -n \"$script\"" in workflow
    assert "if: github.event_name == 'workflow_dispatch'" in workflow
    assert "appleboy/ssh-action@029f5b4aeeeb58fdfe1410a5d17f967dacf36262" in workflow
