from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_privileged_assets_are_staged_before_operational_phases() -> None:
    installer = read("installer/install.sh")
    assert installer.index("run_phase 00_trusted_assets") < installer.index("run_phase 03_service_user")
    assert installer.index("run_phase 00_trusted_assets") < installer.index("run_phase 04_directories")
    assert installer.index("cleanup_trusted_installer_assets") > installer.index("write_summary")


def test_resume_reexecutes_root_private_runner_before_loading_repository_libraries() -> None:
    installer = read("installer/install.sh")
    first_source = installer.index('source "$INSTALLER_DIR/lib/colors.sh"')
    resume_exec = installer.index('exec /usr/local/sbin/telz-installer-resume "$@"')
    assert resume_exec < first_source
    assert "TELZ_TRUSTED_INSTALLER_RUNNER" in installer

    system = read("installer/lib/system.sh")
    for asset in (
        "installer/install.sh",
        "installer/config/defaults.env",
        "installer/lib/system.sh",
        "installer/lib/validation.sh",
    ):
        assert asset in system
    assert "/usr/local/sbin/telz-installer-resume" in system
    assert "sha256sum --check --strict .manifest.sha256" in system


def test_resume_state_is_bound_to_effective_configuration() -> None:
    installer = read("installer/install.sh")
    assert 'CONFIG_FINGERPRINT_FILE="$STATE_DIR/config.sha256"' in installer
    assert '"$(<"$CONFIG_FINGERPRINT_FILE")" == "$CONFIG_FINGERPRINT"' in installer
    assert "Configuracao efetiva divergiu" in installer
    for key in ("INSTALL_DIR", "SERVICE_USER", "PLATFORM_DOMAIN", "API_PORT", "WEB_PORT", "API_WORKERS"):
        assert key in installer[installer.index("CONFIG_FINGERPRINT=") :]
    for secret in ("DATABASE_PASSWORD", "JWT_SECRET_KEY", "ADMIN_PASSWORD", "MERCADO_PAGO_ACCESS_TOKEN", "ASAAS_API_KEY"):
        assert secret in installer[installer.index("CONFIG_FINGERPRINT=") :]


def test_external_config_is_trusted_before_root_sources_it() -> None:
    installer = read("installer/install.sh")
    config_block = installer[installer.index('if [[ -n "$CONFIG_FILE" ]]') : installer.index('TELZ_NON_INTERACTIVE=')]
    assert '[[ "$CONFIG_FILE_INPUT" = /* ]]' in config_block
    assert 'realpath -e -- "$CONFIG_FILE_INPUT"' in config_block
    assert '"$(stat -c \'%U\' "$CONFIG_FILE")" == "root"' in config_block
    assert '-perm /022' in config_block
    assert 'source "$CONFIG_FILE"' in config_block
    assert config_block.index('"$(stat -c \'%U\' "$CONFIG_FILE")" == "root"') < config_block.index('source "$CONFIG_FILE"')


def test_snapshot_copy_uses_descriptor_relative_nofollow_and_manifest() -> None:
    system = read("installer/lib/system.sh")
    stage = system[system.index("stage_trusted_installer_assets()") : system.index("load_trusted_installer_assets()")]
    assert "os.O_NOFOLLOW" in stage
    assert "dir_fd=source_dir_fd" in stage
    assert '".manifest.sha256"' in stage
    assert "validate_trusted_installer_asset_dir" in stage
    assert "sudo -u" not in stage


def test_privileged_consumers_only_use_trusted_assets() -> None:
    consumers = {
        "installer/lib/systemd.sh": (
            "scripts/collect-telz-monitoring.sh",
            "scripts/health-check.sh",
            "installer/templates/telz-api.service",
        ),
        "installer/lib/nginx.sh": ("installer/templates/nginx-telz.conf",),
        "installer/lib/ssl.sh": ("scripts/finish-ssl.sh",),
        "installer/lib/backup.sh": ("scripts/backup-telz.sh",),
    }
    for path, assets in consumers.items():
        contents = read(path)
        for asset in assets:
            assert f"trusted_installer_asset {asset}" in contents


def test_installer_validates_path_user_domain_ports_and_workers() -> None:
    installer = read("installer/install.sh")
    validation = read("installer/lib/validation.sh")
    for gate in (
        'validate_install_dir "$INSTALL_DIR"',
        'validate_service_user "$SERVICE_USER"',
        'validate_domain "$PLATFORM_DOMAIN"',
        'validate_worker_count "${API_WORKERS:-2}"',
    ):
        assert gate in installer
    assert "realpath -m" in validation
    assert "^/opt/" in validation
    assert '"$value" == "root"' in validation
    assert '"$1" -le 65535' in validation


def test_frontend_toolchain_is_pinned_and_uses_root_private_staging() -> None:
    frontend = read("installer/lib/frontend.sh")
    assert "node_22.x" in frontend
    assert "npm install -g --ignore-scripts pnpm@10.14.0" in frontend
    assert "/var/lib/telz-installer/nodesource.XXXXXX" in frontend
    assert "/tmp/nodesource" not in frontend


@pytest.mark.parametrize(
    ("function", "value"),
    (
        ("validate_install_dir", "/"),
        ("validate_install_dir", "/opt/telz/../../etc"),
        ("validate_service_user", "root"),
        ("validate_service_user", "bad user"),
        ("validate_domain", "https://erp.telz.com.br"),
        ("validate_domain", "bad_domain"),
        ("validate_port", "0"),
        ("validate_port", "65536"),
        ("validate_worker_count", "0"),
        ("validate_worker_count", "65"),
    ),
)
def test_validation_rejects_unsafe_values(function: str, value: str) -> None:
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash indisponivel")
    validation = (ROOT / "installer/lib/validation.sh").as_posix()
    command = f'fail() {{ return 1; }}; source "$1"; "$2" "$3"'
    result = subprocess.run(
        [bash, "-c", command, "bash", validation, function, value],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0, result.stdout + result.stderr
