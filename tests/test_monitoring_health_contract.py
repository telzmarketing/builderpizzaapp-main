from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def bash_executable() -> str:
    candidate = shutil.which("bash")
    if candidate and not (os.name == "nt" and "system32" in candidate.lower()):
        return candidate
    if os.name == "nt":
        git_bash = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git" / "bin" / "bash.exe"
        if git_bash.is_file():
            return str(git_bash)
    pytest.skip("bash compativel indisponivel")


def run_nginx_probe(tmp_path: Path, *, output: str = "", exit_code: int | None = 0) -> subprocess.CompletedProcess[str]:
    collector = (ROOT / "scripts/collect-telz-monitoring.sh").read_text(encoding="utf-8")
    match = re.search(r"^nginx_probe\(\) \{.*?^\}\r?$", collector, flags=re.MULTILINE | re.DOTALL)
    assert match is not None

    fake_nginx = tmp_path / "nginx"
    if exit_code is not None:
        fake_nginx.write_text(
            "#!/usr/bin/env bash\n"
            f"printf '%s\\n' {output!r} >&2\n"
            f"exit {exit_code}\n",
            encoding="utf-8",
        )
        fake_nginx.chmod(0o700)

    function_source = match.group(0).replace("/usr/sbin/nginx", fake_nginx.as_posix())
    script = f"set -Eeuo pipefail\n{function_source}\nnginx_probe\n"
    return subprocess.run(
        [bash_executable(), "-c", script],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_monitoring_health_snapshot_includes_database_probe() -> None:
    collector = (ROOT / "scripts/collect-telz-monitoring.sh").read_text(encoding="utf-8")

    assert 'export TELZ_MONITOR_DB_OK="$DB_OK"' in collector
    assert 'database_status = ("healthy", "ok") if flag("TELZ_MONITOR_DB_OK") else ("critical", "unreachable")' in collector
    assert 'component("database", *database_status)' in collector


def test_nginx_probe_has_sanitized_semantic_results() -> None:
    collector = (ROOT / "scripts/collect-telz-monitoring.sh").read_text(encoding="utf-8")

    assert "NGINX_OK" not in collector
    assert "NGINX_RESULT=\"$(nginx_probe)\"" in collector
    assert "if [[ ! -x /usr/sbin/nginx ]]" in collector
    assert "if /usr/sbin/nginx -t" in collector
    assert "paths, hostnames, or configuration fragments" in collector
    for result in (
        "ok",
        "config_invalid",
        "permission_denied",
        "binary_unavailable",
        "execution_failed",
    ):
        assert f'"{result}"' in collector or f"result={result}" in collector


@pytest.mark.parametrize(
    ("output", "exit_code", "expected"),
    [
        ("configuration test is successful", 0, "ok"),
        ("[emerg] unknown directive invalid_example", 1, "config_invalid"),
        ('open() "/run/nginx.pid" failed (13: Permission denied)', 1, "permission_denied"),
        ("unexpected operating failure", 2, "execution_failed"),
    ],
)
def test_nginx_probe_classifies_execution_without_leaking_output(
    tmp_path: Path, output: str, exit_code: int, expected: str
) -> None:
    result = run_nginx_probe(tmp_path, output=output, exit_code=exit_code)

    assert result.returncode == 0, result.stderr
    assert result.stdout == expected
    assert f"resultado={expected}" in result.stderr
    assert output not in result.stderr


def test_nginx_probe_classifies_missing_binary(tmp_path: Path) -> None:
    result = run_nginx_probe(tmp_path, exit_code=None)

    assert result.returncode == 0, result.stderr
    assert result.stdout == "binary_unavailable"
    assert "resultado=binary_unavailable" in result.stderr


def test_monitoring_sandbox_hides_live_nginx_pid_without_broad_write_access() -> None:
    unit = (ROOT / "installer/templates/telz-monitoring.service").read_text(encoding="utf-8")

    assert "ProtectSystem=strict" in unit
    assert "BindPaths=/dev/null:/run/nginx.pid" in unit
    assert "ReadWritePaths=/run" not in unit
    assert "ReadWritePaths=/var" not in unit
    assert "ReadWritePaths=/etc" not in unit


def test_platform_health_exposes_all_nginx_probe_messages() -> None:
    service = (ROOT / "backend/services/platform_health_service.py").read_text(encoding="utf-8")

    for result in (
        "config_invalid",
        "permission_denied",
        "binary_unavailable",
        "execution_failed",
    ):
        assert f'"{result}":' in service


def test_updater_reinstalls_corrected_monitoring_assets_and_resume_rechecks_health() -> None:
    updater = (ROOT / "scripts/update-telz.sh").read_text(encoding="utf-8")
    installer = (ROOT / "installer/install.sh").read_text(encoding="utf-8")

    assert 'install -m 0755 -o root -g root "$BUNDLE_HEALTH" "$HEALTH_COMMAND"' in updater
    assert 'install -m 0755 -o root -g root "$BUNDLE_COLLECTOR" "$COLLECTOR_COMMAND"' in updater
    assert '"$BUNDLE_MONITOR_UNIT" > "$UNIT_STAGE_DIR/telz-monitoring.service"' in updater
    assert updater.index("systemd-analyze verify") < updater.index(
        'install -m 0644 -o root -g root "$unit_file"'
    )
    assert installer.rindex('run_phase 16_backup install_backup_cron') < installer.index(
        'info "Executando health check final"'
    )


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
