from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_maintenance_lock_is_root_private_regular_and_never_truncated():
    for relative in (
        "scripts/backup-telz.sh",
        "scripts/restore-telz.sh",
        "scripts/rollback-telz.sh",
        "scripts/finish-ssl.sh",
    ):
        source = read(relative)
        assert 'MAINTENANCE_LOCK_DIR="/run/lock/telz"' in source
        assert 'root:root:700' in source
        assert 'root:root:600:1' in source
        assert 'exec 9<>"$MAINTENANCE_LOCK"' in source or relative.endswith("backup-telz.sh")
        assert 'exec 9>"$MAINTENANCE_LOCK"' not in source
    backup = read("scripts/backup-telz.sh")
    assert 'stat -Lc \'%d:%i\' "/proc/$$/fd/9"' in backup
    assert 'fd 9 herdado nao possuia lock preexistente' in backup


def test_backup_quiesces_before_snapshot_and_preserves_signal_recovery():
    backup = read("scripts/backup-telz.sh")
    assert backup.index("stop_writers") < backup.index('pg_dump --format=custom')
    assert backup.index("stop_writers") < backup.index('tar -C "$INSTALL_DIR"')
    assert '"consistency": "quiesced_snapshot"' in backup
    assert "trap 'on_error 143' TERM HUP" in backup
    assert "trap 'on_error 130' INT" in backup
    assert "trap 'exit 143' TERM HUP" not in backup
    assert backup.index("restore_service_state") < backup.rindex("ERROR_HANDLER_ARMED=false")
    assert backup.rindex("validate_recovered_services") < backup.rindex("SERVICES_QUIESCED=false")
    assert backup.rindex("SERVICES_QUIESCED=false") < backup.rindex("ERROR_HANDLER_ARMED=false")


def test_backup_normal_health_failure_reaches_one_fail_closed_err_handler():
    backup = read("scripts/backup-telz.sh")
    normal_recovery = backup[backup.rindex("\nrestore_service_state\n") :]
    assert "\nvalidate_recovered_services\n" in normal_recovery
    assert 'run_recovery_step "health local apos snapshot"' not in normal_recovery
    assert normal_recovery.index("validate_recovered_services") < normal_recovery.index("SERVICES_QUIESCED=false")
    assert normal_recovery.index("SERVICES_QUIESCED=false") < normal_recovery.index("ERROR_HANDLER_ARMED=false")


def test_database_credentials_never_enter_postgres_tool_argv():
    backup = read("scripts/backup-telz.sh")
    restore = read("scripts/restore-telz.sh")
    assert 'pg_dump --format=custom "$DATABASE_URL"' not in backup
    assert '--dbname="$CURRENT_DATABASE_URL"' not in restore
    assert "PGPASSFILE=" in backup and "PGDATABASE=" in backup
    assert "PGPASSFILE=" in restore and "PGDATABASE=" in restore
    assert "--single-transaction" in restore
    assert "TELZ_ALLOW_DATABASE_URL_CHANGE" not in restore


def test_restore_stages_then_quiesces_then_takes_safety_backup_before_mutation():
    restore = read("scripts/restore-telz.sh")
    extraction = restore.index('--no-same-owner --no-same-permissions')
    stop = restore.rindex("\nstop_services\n")
    safety = restore.index('echo "[restore] criando safety backup coerente')
    mutation = restore.index('echo "[restore] restaurando PostgreSQL')
    assert extraction < stop < safety < mutation
    assert restore.index('validate_database_revision "$MANIFEST_REVISION"') < restore.index("UPLOADS_OLD_MOVED=true")
    assert 'database_identity_fingerprint "$BACKUP_SET/environment.env"' in restore
    assert '"$BACKUP_SET/environment.env" "$INSTALL_DIR/backend/.env"' not in restore
    assert 'TELZ_ALEMBIC_TARGET="$MANIFEST_REVISION"' in restore


def test_rollback_only_swaps_release_and_fails_closed_after_recovery_health():
    rollback = read("scripts/rollback-telz.sh")
    for forbidden in ("git checkout", "pip install", "pnpm install", "run build", "alembic downgrade"):
        assert forbidden not in rollback
    assert 'TARGET_CODE_DIR="$(validate_release_path' in rollback
    assert 'mv -Tf -- "$temporary" "$CURRENT_LINK"' in rollback
    assert 'find "$release_real" -xdev ! -user root -print -quit' in rollback
    assert 'find "$release_real" -xdev \\( -type d -o -type f \\) -perm /022' in rollback
    assert "release possui symlink externo nao autorizado" in rollback
    assert 'run_recovery_step "parada fail-closed dos servicos" stop_services' in rollback


def test_release_consumers_use_v2_and_query_db_without_legacy_migration_graph():
    consumers = (
        "scripts/backup-telz.sh",
        "scripts/restore-telz.sh",
        "scripts/rollback-telz.sh",
        "scripts/health-check.sh",
    )
    for relative in consumers:
        source = read(relative)
        assert 'data.get("schema_version") != 2' in source
        assert "dependency_artifact_sha256" in source
        assert "public_build_config_sha256" in source
        assert "legacy_compat" in source
        assert "SELECT version_num FROM alembic_version" in source
        assert "20260817_platform_wave0:20260818_platform_operations" in source
    health = read("scripts/health-check.sh")
    collector = read("scripts/collect-telz-monitoring.sh")
    assert 'validate_monitor_snapshot "$SNAPSHOT"' in health
    assert 'CODE_DIR="$(realpath -e "$CURRENT_LINK")"' in collector
    assert 'BACKUP_RUN_ID = re.compile(r"^[0-9]{8}-[0-9]{6}-[0-9]+$")' in collector
