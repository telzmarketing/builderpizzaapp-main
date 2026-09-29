from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_monitoring_health_snapshot_includes_database_probe() -> None:
    collector = (ROOT / "scripts/collect-telz-monitoring.sh").read_text(encoding="utf-8")

    assert 'export TELZ_MONITOR_DB_OK="$DB_OK"' in collector
    assert 'database_status = ("healthy", "ok") if flag("TELZ_MONITOR_DB_OK") else ("critical", "unreachable")' in collector
    assert 'component("database", *database_status)' in collector


def test_runtime_units_make_code_read_only_and_limit_writable_state() -> None:
    api = (ROOT / "installer/templates/telz-api.service").read_text(encoding="utf-8")
    gateway = (ROOT / "installer/templates/telz-whatsapp-gateway.service").read_text(encoding="utf-8")

    for unit in (api, gateway):
        assert "ProtectSystem=strict" in unit
        assert "ProtectHome=yes" in unit
        assert "PrivateTmp=yes" in unit
        assert "NoNewPrivileges=yes" in unit
    assert "ReadWritePaths=__INSTALL_DIR__/uploads" in api
    assert "ReadWritePaths=__INSTALL_DIR__/.runtime/baileys" in gateway
