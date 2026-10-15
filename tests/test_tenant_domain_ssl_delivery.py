"""Guard the privileged worker's delivery and recovery boundary."""
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = {
    "scripts/tenant-domain-ssl.py",
    "scripts/tenant-domain-ssl-renew-hook.py",
    "installer/templates/telz-domain-ssl.service",
    "installer/templates/telz-domain-ssl.timer",
}


def test_every_delivery_path_seals_the_worker_and_its_units():
    for name in (
        "scripts/update-telz.sh",
        "scripts/deploy-telz-from-origin.sh",
        "scripts/deploy-telz-artifacts-manually.sh",
        ".github/workflows/deploy.yml",
        ".github/workflows/prepare-manual-deploy.yml",
        "installer/lib/system.sh",
    ):
        source = (ROOT / name).read_text(encoding="utf-8")
        assert ARTIFACTS <= set(re.findall(r"(?:scripts|installer/templates)/[a-zA-Z0-9_.-]+", source)), name


def test_recovery_snapshot_keys_match_their_privileged_destinations():
    source = (ROOT / "scripts/update-telz.sh").read_text(encoding="utf-8")
    paths = re.search(r"OPERATIONS_PATHS=\((.*?)\n\)", source, re.S).group(1).split()
    keys = re.search(r"OPERATIONS_KEYS=\((.*?)\n\)", source, re.S).group(1).split()
    assert len(paths) == len(keys)
    pairs = dict(zip(paths, keys))
    assert pairs["/usr/local/sbin/telz-domain-ssl"] == "telz-domain-ssl"
    assert pairs["/etc/letsencrypt/renewal-hooks/deploy/telz-domain-ssl"] == "telz-domain-ssl-renew-hook"
    assert pairs["/etc/systemd/system/telz-domain-ssl.service"] == "telz-domain-ssl.service"
    assert pairs["/etc/systemd/system/telz-domain-ssl.timer"] == "telz-domain-ssl.timer"
    assert pairs["/etc/telz/domain-ssl.json"] == "telz-domain-ssl.config"
    assert pairs["/var/lib/telz/domain-ssl/runtime.json"] == "telz-domain-ssl.runtime"
    assert pairs["/etc/cron.d/telz-backup"] == "telz-backup.cron"


def test_update_bootstraps_only_after_activation_and_final_health_with_validated_helper():
    source = (ROOT / "scripts/update-telz.sh").read_text(encoding="utf-8")
    bootstrap = source.index('if TELZ_MAINTENANCE_LOCK_HELD=true /usr/bin/python3 -I /usr/local/sbin/telz-domain-ssl')
    assert source.index('\nactivate_release\n') < source.rindex('"$HEALTH_COMMAND" "$INSTALL_DIR"') < bootstrap
    assert source.index('require_root_owned_executable /usr/local/sbin/telz-domain-ssl') < bootstrap
    assert '--platform-hostnames "$DOMAIN_SSL_PLATFORM_HOST"' in source[bootstrap:]
    assert '--service-user "$SERVICE_USER" --install-dir "$INSTALL_DIR"' in source[bootstrap:]
    assert 'from urllib.parse import urlsplit' in source
    assert 'executor HTTPS indisponivel' in source[bootstrap:]
    assert source.index('\nRECOVERY_REQUIRED=false\n', bootstrap) > bootstrap
    unit = (ROOT / "installer/templates/telz-domain-ssl.service").read_text(encoding="utf-8")
    assert "ConditionPathExists=/etc/telz/domain-ssl.json" in unit
    assert "ExecStart=/usr/bin/python3 -I /usr/local/sbin/telz-domain-ssl" in unit


def test_update_restores_ssl_timer_states_and_never_builds_two_manifests_for_same_sha():
    source = (ROOT / "scripts/update-telz.sh").read_text(encoding="utf-8")
    assert 'SSL_TIMERS=(telz-domain-ssl.timer certbot.timer)' in source
    assert 'SSL_TIMER_WAS_ENABLED["$timer"]="$(systemctl is-enabled "$timer"' in source
    assert 'SSL_TIMER_WAS_ACTIVE["$timer"]="$(systemctl is-active "$timer"' in source
    restore = source.split('restore_operational_artifacts() {', 1)[1].split('\nunit_exists()', 1)[0]
    assert 'systemctl stop "$timer"' in restore
    assert 'systemctl enable "$timer"' in restore
    assert 'systemctl disable "$timer"' in restore
    assert 'systemctl start "$timer"' in restore
    assert '"${SSL_TIMER_WAS_ACTIVE[$timer]}" == "active"' in restore
    assert 'if [[ -z "$PREVIOUS_CURRENT_TARGET" && "$PREVIOUS_ACTIVE_COMMIT" != "$EXPECTED_COMMIT" ]]; then\n  materialize_rollback_release' in source
