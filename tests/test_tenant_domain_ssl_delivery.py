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
    assert pairs["/etc/cron.d/telz-backup"] == "telz-backup.cron"


def test_delivery_does_not_enable_issuance_without_operator_configuration():
    for name in ("scripts/update-telz.sh", "installer/lib/systemd.sh"):
        source = (ROOT / name).read_text(encoding="utf-8")
        for line in source.splitlines():
            if "systemctl enable" in line:
                assert "telz-domain-ssl" not in line
    unit = (ROOT / "installer/templates/telz-domain-ssl.service").read_text(encoding="utf-8")
    assert "ConditionPathExists=/etc/telz/domain-ssl.json" in unit
    assert "ExecStart=/usr/bin/python3 -I /usr/local/sbin/telz-domain-ssl" in unit
