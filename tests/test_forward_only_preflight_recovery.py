from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UPDATER = (ROOT / "scripts/update-telz.sh").read_text(encoding="utf-8")
HEALTH = (ROOT / "scripts/health-check.sh").read_text(encoding="utf-8")


def test_forward_only_retry_recovers_previous_services_before_preflight():
    recovery = UPDATER.index("recover_forward_only_preflight_services()")
    preflight_health = UPDATER.index('TELZ_ALEMBIC_TARGET="$DATABASE_CURRENT"')

    assert recovery < preflight_health
    assert '[[ -e "$FORWARD_CUTOVER_MARKER" && ! -L "$FORWARD_CUTOVER_MARKER" ]]' in UPDATER
    assert '[[ "$DATABASE_CURRENT" == "$PREVIOUS_ACTIVE_REVISION" ]]' in UPDATER
    assert "systemctl start telz-api telz-web" in UPDATER


def test_health_reports_the_specific_inactive_service():
    assert "require_active_service()" in HEALTH
    assert 'die "servico $unit inativo (estado=$state)"' in HEALTH
    assert "require_active_service telz-api" in HEALTH
    assert "require_active_service telz-web" in HEALTH
    assert "require_active_service telz-whatsapp-gateway" in HEALTH


def test_preflight_failure_is_labeled_and_failed_migration_is_not_assumed_applied():
    assert 'die "preflight health falhou antes da mutacao"' in UPDATER
    attempted = UPDATER.index("MIGRATION_ATTEMPTED=true")
    alembic = UPDATER.index('alembic_at "$FINAL_APP_DIR" upgrade "$ALEMBIC_TARGET"')
    confirmed = UPDATER.index("MIGRATION_APPLIED=true", alembic)

    assert attempted < alembic < confirmed
    assert "FAILED_MIGRATION_CURRENTS" in UPDATER


def test_successful_cutover_clears_recovery_marker_only_at_end():
    marker_clear = UPDATER.index('rm -f -- "$FORWARD_CUTOVER_MARKER"')
    final_state = UPDATER.index("MAINTENANCE_WINDOW=false", marker_clear)

    assert marker_clear < final_state
