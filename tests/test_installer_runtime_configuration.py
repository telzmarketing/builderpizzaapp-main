from pathlib import Path
import os
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def run_bash(script: str, *arguments: str) -> subprocess.CompletedProcess[str]:
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash indisponivel")
    if os.name == "nt" and "system32" in bash.lower():
        pytest.skip("bash via WSL nao preserva o cwd do processo Windows")
    return subprocess.run(
        [bash, "-c", script, "bash", *arguments],
        check=False,
        capture_output=True,
        text=True,
    )


def test_database_url_percent_encodes_credentials() -> None:
    validation = "installer/lib/validation.sh"
    database = "installer/lib/database.sh"
    result = run_bash(
        "source \"$1\"; source \"$2\"; "
        "DATABASE_MODE=local; DATABASE_USER=telz_user; "
        "DATABASE_PASSWORD='a@b:c/%?#'; DATABASE_PORT=5432; DATABASE_NAME=telz; "
        "build_database_url; printf '%s' \"$DATABASE_URL\"",
        validation,
        database,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "postgresql://telz_user:a%40b%3Ac%2F%25%3F%23@127.0.0.1:5432/telz"


def test_existing_local_database_role_has_its_password_reconciled() -> None:
    database = read("installer/lib/database.sh")

    assert "ALTER USER %s WITH PASSWORD %s" in database
    assert "CREATE USER %s WITH PASSWORD %s" in database
    assert 'psql -v ON_ERROR_STOP=1 -c "CREATE USER' not in database


@pytest.mark.parametrize("value", ("externalx", "externl", "LOCAL", ""))
def test_database_mode_rejects_unknown_values(value: str) -> None:
    validation = "installer/lib/validation.sh"
    result = run_bash(
        'fail() { printf "%s" "$1" >&2; }; source "$1"; validate_database_mode "$2"',
        validation,
        value,
    )
    assert result.returncode != 0


@pytest.mark.parametrize("value", ("/", "/tmp/telz-monitoring", "/var/lib/telz/../outside"))
def test_monitoring_dir_rejects_paths_outside_private_state(value: str) -> None:
    result = run_bash(
        'fail() { printf "%s" "$1" >&2; }; source "$1"; validate_monitoring_dir "$2"',
        "installer/lib/validation.sh",
        value,
    )
    assert result.returncode != 0


def test_runtime_flags_gate_their_commands() -> None:
    installer = read("installer/install.sh")
    frontend = read("installer/lib/frontend.sh")
    database = read("installer/lib/database.sh")
    assert 'if ! is_true "$RUN_ALEMBIC"' in database
    assert 'HEALTH_ALEMBIC_TARGET=""' in installer
    assert 'if is_true "$RUN_ALEMBIC"; then' in installer
    for flag in ("RUN_TYPECHECK", "RUN_TESTS", "RUN_BUILD"):
        assert f'if is_true "${flag}"' in frontend


def test_installer_validates_booleans_and_ssl_nginx_dependency() -> None:
    installer = read("installer/install.sh")
    validation = read("installer/lib/validation.sh")
    assert 'normalize_boolean "$boolean_name"' in installer
    assert 'if is_true "$INSTALL_SSL" && ! is_true "$INSTALL_NGINX"' in installer
    assert 'fail "$name deve ser booleano (true ou false)"' in validation
    assert 'fail "$gated_flag deve permanecer false na instalacao inicial' in installer


def test_installer_holds_global_lock_and_cleans_env_staging() -> None:
    installer = read("installer/install.sh")
    backend = read("installer/lib/backend.sh")
    assert 'INSTALLER_LOCK_FILE="$INSTALLER_LOCK_DIR/install.lock"' in installer
    assert 'flock -n 8' in installer
    assert 'trap cleanup_installer_temporary_files EXIT' in installer
    assert 'BACKEND_ENV_STAGING_FILE="$env_temp"' in backend


def test_custom_runtime_configuration_reaches_health_monitor_and_cron() -> None:
    installer = read("installer/install.sh")
    systemd = read("installer/lib/systemd.sh")
    monitor_unit = read("installer/templates/telz-monitoring.service")
    backup = read("installer/lib/backup.sh")
    for assignment in (
        'TELZ_SERVICE_USER="$SERVICE_USER"',
        'TELZ_HEALTH_API_PORT="$API_PORT"',
        'TELZ_HEALTH_WEB_PORT="$WEB_PORT"',
        'TELZ_MONITORING_DIR="$PLATFORM_MONITORING_SNAPSHOT_DIR"',
    ):
        assert assignment in installer
    assert "__MONITORING_DIR__" in monitor_unit
    assert 's#__MONITORING_DIR__#${PLATFORM_MONITORING_SNAPSHOT_DIR}#g' in systemd
    for assignment in (
        "TELZ_SERVICE_USER=${SERVICE_USER}",
        "TELZ_HEALTH_API_PORT=${API_PORT}",
        "TELZ_HEALTH_WEB_PORT=${WEB_PORT}",
        "TELZ_MONITORING_DIR=${PLATFORM_MONITORING_SNAPSHOT_DIR}",
    ):
        assert assignment in backup


def test_requested_ssl_failure_is_not_swallowed_and_summary_matches_protocol() -> None:
    ssl = read("installer/lib/ssl.sh")
    summary = read("installer/lib/summary.sh")
    assert '"$ssl_helper" "$PLATFORM_DOMAIN" "$SSL_EMAIL"' in ssl
    assert "SSL nao concluido" not in ssl
    assert "health_public=http://%s/health" in summary
    assert "health_public=https://%s/health" in summary
    assert "health_public=disabled" in summary


def test_firewall_allows_detected_ssh_ports_before_enabling_ufw() -> None:
    firewall = read("installer/lib/firewall.sh")
    assert 'sshd_effective="$(sshd -T 2>/dev/null)"' in firewall
    assert 'connection_port="${ssh_connection_fields[3]:-}"' in firewall
    assert firewall.index('ufw allow "${port}/tcp"') < firewall.index("ufw --force enable")


def test_summary_reports_fixed_unit_names() -> None:
    summary = read("installer/lib/summary.sh")
    assert "api_service=telz-api" in summary
    assert "web_service=telz-web" in summary
    assert "%s-api" not in summary


def test_installer_persists_root_owned_operational_configuration() -> None:
    installer = read("installer/install.sh")
    system = read("installer/lib/system.sh")
    assert "run_phase 13_operational_config persist_operational_config" in installer
    assert 'local config_file="$config_dir/operations.conf"' in system
    assert 'chmod 0600 "$temporary"' in system
    assert 'chown root:root "$temporary"' in system
    for key in (
        "SERVICE_USER",
        "API_PORT",
        "WEB_PORT",
        "API_WORKERS",
        "WHATSAPP_GATEWAY_PORT",
        "INSTALL_WHATSAPP_GATEWAY",
        "INSTALL_BACKUP",
        "PLATFORM_MONITORING_SNAPSHOT_DIR",
    ):
        assert f"printf '{key}=%s\\n'" in system


def test_updater_parses_operational_config_without_sourcing_it() -> None:
    updater = read("scripts/update-telz.sh")
    parser = updater[updater.index("load_operational_config()") : updater.index("validate_operational_config()")]
    assert 'OPERATION_CONFIG_FILE="/etc/telz/operations.conf"' in updater
    assert 'done < "$config_file"' in parser
    assert 'source "$config_file"' not in parser
    assert '. "$config_file"' not in parser
    assert '*) die "chave operacional desconhecida: $key"' in parser
    assert '[[ "${seen[$key]:-}" == "true" ]]' in parser
    assert "fallback legado validado" in updater


def test_updater_propagates_runtime_values_and_converges_optional_services() -> None:
    updater = read("scripts/update-telz.sh")
    for assignment in (
        'TELZ_SERVICE_USER="$SERVICE_USER"',
        'TELZ_HEALTH_API_PORT="$API_PORT"',
        'TELZ_HEALTH_WEB_PORT="$WEB_PORT"',
        'TELZ_MONITORING_DIR="$MONITORING_DIR"',
    ):
        assert updater.count(assignment) >= 2
    assert 'if [[ "$GATEWAY_ENABLED" == "true" ]]; then' in updater
    assert "rm -f -- /etc/systemd/system/telz-whatsapp-gateway.service" in updater
    assert 'if [[ "$BACKUP_ENABLED" == "true" ]]; then' in updater
    assert "rm -f -- /etc/cron.d/telz-backup" in updater
    assert 'install -d -m 0750 -o root -g "$SERVICE_USER" "$MONITORING_DIR"' in updater


def test_installer_converges_disabled_gateway_and_backup() -> None:
    systemd = read("installer/lib/systemd.sh")
    backup = read("installer/lib/backup.sh")
    assert "systemctl disable --now telz-whatsapp-gateway" in systemd
    assert "rm -f -- /etc/systemd/system/telz-whatsapp-gateway.service" in systemd
    assert backup.index("rm -f -- /etc/cron.d/telz-backup") < backup.index(
        'info "Backup automatico desabilitado."'
    )
