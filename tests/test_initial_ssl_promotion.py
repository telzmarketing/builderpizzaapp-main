import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys

import pytest


ROOT = Path(__file__).parents[1]
SOURCE = (ROOT / "installer/install.sh").read_text(encoding="utf-8")
SHA = "a" * 40
REVISION = "20261014_tenant_domain_ssl"


def run_promotion(*, current=False, resume=False, branch="main", valid=True, healthy=True, bootstrap=True):
    bash = shutil.which("bash")
    if os.name == "nt" and (not bash or "system32" in bash.lower()):
        candidate = Path("C:/Program Files/Git/bin/bash.exe")
        bash = str(candidate) if candidate.exists() else None
    if not bash:
        pytest.skip("Native bash unavailable")
    function = SOURCE[SOURCE.index("promote_initial_release() {"):SOURCE.index("run_phase 17_immutable_release")]
    function = function.replace('[[ -e /var/lib/telz/current || -L /var/lib/telz/current ]]', '[[ "$MOCK_CURRENT" == true ]]')
    function = function.replace("/usr/local/sbin/telz-deploy-from-origin", "mock_deploy")
    function = function.replace("/usr/local/sbin/telz-health-check", "mock_health")
    function = function.replace("/usr/bin/python3", "mock_python")
    script = f"""
unset TELZ_LEGACY_ADOPTION TELZ_SERVICE_USER TELZ_ALEMBIC_TARGET
is_true() {{ [[ "$1" == true ]]; }}
fail() {{ printf '%s\\n' "$1" >&2; }}
warn() {{ printf 'warn:%s\\n' "$1"; }}
info() {{ printf 'info:%s\\n' "$1"; }}
sudo() {{ printf '%s\\n' '{SHA}'; }}
validate_initial_active_release() {{ printf 'validate:%s\\n' "$1"; return {0 if valid else 1}; }}
mock_health() {{ printf 'health:%s:%s\\n' "$TELZ_SERVICE_USER" "$TELZ_ALEMBIC_TARGET"; return {0 if healthy else 1}; }}
mock_python() {{ printf 'bootstrap:%s\\n' "$*"; return {0 if bootstrap else 1}; }}
mock_deploy() {{ printf 'deploy:%s:%s:%s:%s\\n' "$TELZ_SERVICE_USER" "$TELZ_ALEMBIC_TARGET" "$TELZ_LEGACY_ADOPTION" "$1"; }}
SERVICE_USER=customtelz; INSTALL_DIR=/opt/custom; PLATFORM_DOMAIN=app.telz.com.br
INSTALL_SSL=true; RUN_ALEMBIC=true; GIT_BRANCH={branch}; ALEMBIC_TARGET={REVISION}
API_PORT=8100; WEB_PORT=3100; PLATFORM_MONITORING_SNAPSHOT_DIR=/var/lib/telz/monitoring
PLATFORM_PUBLIC_IP=8.8.8.8; TENANT_DOMAINS_PLATFORM_HOSTNAMES=admin.telz.com.br
MOCK_CURRENT={'true' if current else 'false'}; RESUME={'true' if resume else 'false'}
{function}
promote_initial_release
"""
    return subprocess.run([bash, "-c", script], capture_output=True, text=True, timeout=20)


def test_initial_same_sha_promotion_passes_collected_service_and_revision():
    result = run_promotion()
    assert result.returncode == 0, result.stderr
    assert f"deploy:customtelz:{REVISION}:true:{SHA}" in result.stdout
    assert "--public-ips 8.8.8.8" in result.stdout
    assert "--platform-hostnames app.telz.com.br,admin.telz.com.br" in result.stdout
    assert result.stdout.index("deploy:") < result.stdout.index("bootstrap:")


def test_initial_bootstrap_failure_does_not_mark_promotion_complete():
    result = run_promotion(bootstrap=False)
    assert result.returncode != 0
    assert "deploy:" in result.stdout
    assert "bootstrap:" in result.stdout


def test_non_main_promotion_fails_without_deploy():
    result = run_promotion(branch="release")
    assert result.returncode != 0
    assert "GIT_BRANCH=main" in result.stderr
    assert "deploy:" not in result.stdout


def test_resume_same_sha_revalidates_health_and_bootstrap_without_legacy():
    result = run_promotion(current=True, resume=True)
    assert result.returncode == 0, result.stderr
    assert f"validate:{SHA}" in result.stdout
    assert f"health:customtelz:{REVISION}" in result.stdout
    assert "--bootstrap --service-user customtelz --install-dir /opt/custom" in result.stdout
    assert "deploy:" not in result.stdout


@pytest.mark.parametrize("patch", [{"resume": False}, {"resume": True, "valid": False},
    {"resume": True, "healthy": False}, {"resume": True, "bootstrap": False}])
def test_current_is_never_repromoted_and_failed_resume_never_succeeds(patch):
    result = run_promotion(current=True, **patch)
    assert result.returncode != 0
    assert "deploy:" not in result.stdout


@pytest.mark.parametrize("state", ["valid", "wrong_sha", "wrong_revision", "building", "descriptor_nonroot", "mutable_parent", "duplicate_manifest"])
def test_resume_validator_requires_same_sha_sealed_root_owned_release(tmp_path, monkeypatch, state):
    script = re.search(r"validate_initial_active_release\(\).*?<<'PY'\n(.*?)\nPY", SOURCE, re.S).group(1)
    root = tmp_path / "telz"
    release = root / "releases" / SHA / "app"
    (release / "backend/scripts").mkdir(parents=True)
    (release / "backend/scripts/tenant_domain_ssl_queue.py").write_text("adapter")
    (release / ".venv/bin").mkdir(parents=True)
    (release / ".venv/bin/python").write_text("interpreter fixture")
    current = root / "current"
    current.write_text("symlink fixture")
    manifest = release / ".telz-release.json"
    data = {"schema_version": 2, "status": "building" if state == "building" else "validated",
        "git_commit": "b" * 40 if state == "wrong_sha" else SHA,
        "alembic_revision": "wrong" if state == "wrong_revision" else REVISION}
    manifest.write_text(json.dumps(data) if state != "duplicate_manifest" else '{"status":"validated","status":"building"}')
    original_lstat, original_resolve, original_fstat = Path.lstat, Path.resolve, os.fstat
    def trusted_stat(path, *args, **kwargs):
        info = original_lstat(path, *args, **kwargs)
        values = list(info)
        values[4] = 0
        values[0] = stat.S_IFDIR | 0o755 if stat.S_ISDIR(info.st_mode) else stat.S_IFREG | 0o444
        if path == current:
            values[0], values[3] = stat.S_IFLNK | 0o777, 1
        if state == "mutable_parent" and path == root:
            values[0] = stat.S_IFDIR | 0o777
        return os.stat_result(values)
    def descriptor_stat(fd):
        values = list(original_fstat(fd))
        values[0], values[4] = stat.S_IFREG | 0o444, 1000 if state == "descriptor_nonroot" else 0
        return os.stat_result(values)
    monkeypatch.setattr(Path, "lstat", trusted_stat)
    monkeypatch.setattr(Path, "resolve", lambda path, **kw: release if path == current else original_resolve(path, **kw))
    monkeypatch.setattr(os, "fstat", descriptor_stat)
    monkeypatch.setattr(os, "O_NOFOLLOW", getattr(os, "O_NOFOLLOW", 0), raising=False)
    monkeypatch.setattr(sys, "argv", ["validator", SHA, REVISION])
    script = script.replace("Path('/var/lib/telz')", f"Path({str(root)!r})")
    if state == "valid":
        exec(compile(script, "initial-release-validator", "exec"), {})
    else:
        with pytest.raises((SystemExit, ValueError)):
            exec(compile(script, "initial-release-validator", "exec"), {})
