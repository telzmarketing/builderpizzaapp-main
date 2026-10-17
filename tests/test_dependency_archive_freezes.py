"""Exercise the updater's archive boundary before privileged extraction."""
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import tarfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
TARGET, PREVIOUS = 'a' * 40, 'b' * 40
SECTION = (ROOT / 'scripts/update-telz.sh').read_text(encoding='utf-8').split('require_dependency_archive() {', 1)[1]
VALIDATOR = re.search(r"<<'PY'\n(.*?)\nPY", SECTION, re.S).group(1)


def bundle(tmp_path, *, previous=PREVIOUS, raw=b'Demo==1.0\n', mutation=None):
    public = json.dumps({'VITE_API_URL': '', 'VITE_MULTI_TENANT_AUTH_ENABLED': 'true',
        'VITE_PLATFORM_HOSTNAME': 'app.telz.com.br', 'VITE_PLATFORM_HOSTNAMES': 'app.telz.com.br'}).encode()
    files = {f'python-freezes/{commit}.txt': raw for commit in {TARGET, previous}}
    contracts = {commit: {'python_freeze_sha256': hashlib.sha256(raw).hexdigest(),
        'requirements_sha256': '1' * 64, 'pnpm_lock_sha256': '2' * 64} for commit in {TARGET, previous}}
    metadata = {'schema_version': 1, 'target_commit': TARGET, 'previous_commit': previous,
        'python': '3.12', 'pip': '25.1.1', 'node': '22', 'pnpm': '10.14.0',
        'public_build_config_sha256': hashlib.sha256(public).hexdigest(), 'commits': contracts}
    files['.telz-public-build.json'] = public
    files['.telz-dependencies.json'] = json.dumps(metadata).encode()
    if mutation:
        mutation(files)
    archive_path = tmp_path / 'dependencies.tar.gz'
    with tarfile.open(archive_path, 'w:gz') as archive:
        for name, content in files.items():
            member = tarfile.TarInfo(name)
            if content is None:
                member.type, member.linkname = tarfile.SYMTYPE, '/etc/passwd'
                archive.addfile(member)
            else:
                member.size = len(content)
                archive.addfile(member, io.BytesIO(content))
    return archive_path


def validate(monkeypatch, archive, previous=PREVIOUS):
    monkeypatch.setattr(sys, 'argv', ['validator', str(archive), TARGET, previous])
    exec(compile(VALIDATOR, 'dependency-archive-boundary', 'exec'), {})


@pytest.mark.parametrize('previous', [TARGET, PREVIOUS])
def test_expected_commit_pins_pass(tmp_path, monkeypatch, previous):
    validate(monkeypatch, bundle(tmp_path, previous=previous), previous)


@pytest.mark.parametrize('raw', [b'--index-url https://example.com\n', b'Demo @ https://example.com/a.whl\n',
    b'Demo>=1.0\n', b'Demo==1.0\r\n', b'Demo==1.0', b'z==1\na==1\n',
    b'Demo-Pkg==1\ndemo_pkg==1\n', b'Demo==1\n\n', b''])
def test_invalid_pins_rejected_despite_matching_digest(tmp_path, monkeypatch, raw):
    with pytest.raises(SystemExit):
        validate(monkeypatch, bundle(tmp_path, raw=raw))


@pytest.mark.parametrize('failure', ['missing', 'extra', 'nested', 'symlink', 'hash', 'oversize'])
def test_incomplete_or_unsafe_freezes_rejected(tmp_path, monkeypatch, failure):
    def mutate(files):
        name = f'python-freezes/{TARGET}.txt'
        if failure == 'missing':
            files.pop(name)
        elif failure == 'extra':
            files[f'python-freezes/{"c" * 40}.txt'] = b'Demo==1\n'
        elif failure == 'nested':
            files['python-freezes/nested/pins.txt'] = b'Demo==1\n'
        elif failure == 'symlink':
            files[name] = None
        elif failure == 'hash':
            files[name] = b'Demo==9\n'
        else:
            files[name] = b'x' * 262145
    with pytest.raises(SystemExit):
        validate(monkeypatch, bundle(tmp_path, mutation=mutate))
