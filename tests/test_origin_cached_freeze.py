"""Root reads sealed pins as data; pip still runs only as the build account."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
from types import SimpleNamespace

import pytest

from test_release_cache_contract import content_digest


ROOT = Path(__file__).resolve().parents[1]
COMMIT = '1' * 40


@pytest.fixture
def sealed(tmp_path):
    base = tmp_path / 'releases'
    app = base / COMMIT / 'app'
    source = tmp_path / 'source'
    (app / 'backend').mkdir(parents=True)
    (source / 'backend').mkdir(parents=True)
    for directory in (app, source):
        (directory / 'backend/requirements.txt').write_bytes(b'Example>=1\n')
        (directory / 'pnpm-lock.yaml').write_bytes(b'lockfileVersion: 9\n')
    freeze = b'Example==1.0\nTransit==2.0\n'
    (app / '.telz-python-freeze.txt').write_bytes(freeze)
    hashes = {key: hashlib.sha256((app / name).read_bytes()).hexdigest() for key, name in {
        'python_freeze_sha256': '.telz-python-freeze.txt', 'requirements_sha256': 'backend/requirements.txt',
        'pnpm_lock_sha256': 'pnpm-lock.yaml'}.items()}
    (app / '.telz-build-metadata.json').write_text(json.dumps({'schema_version': 1, 'commit': COMMIT, **hashes}))
    manifest = {'schema_version': 2, 'status': 'validated', 'git_commit': COMMIT,
                'dependency_artifact_sha256': 'a' * 64, **hashes}
    for path in sorted([app, *app.rglob('*')], key=lambda item: len(item.parts), reverse=True):
        path.chmod(0o555 if path.is_dir() else 0o444)
    manifest['content_sha256'] = content_digest(app)
    app.chmod(0o755)
    (app / '.telz-release.json').write_text(json.dumps(manifest))
    (app / '.telz-release.json').chmod(0o444)
    app.chmod(0o555)
    try:
        yield SimpleNamespace(base=base, app=app, source=source, output=tmp_path / 'cached.txt', freeze=freeze)
    finally:
        for path in [app, *app.rglob('*')]:
            path.chmod(0o755 if path.is_dir() else 0o644)


def reader(monkeypatch, sealed, *, wrong_owner=None):
    source = (ROOT / 'scripts/deploy-telz-from-origin.sh').read_text()
    code = re.search(r"prepare_cached_freeze\(\) \{.*?<<'PY'\n(.*?)\nPY", source, re.S).group(1)
    code = code.replace("Path('/var/lib/telz/releases')", 'Path(sys.argv[4])').replace('from pathlib import Path', '')
    # Test-only account/ancestor adaptation: Windows ancestors are not Unix root
    # directories. All paths inside the sealed app keep their real modes/hash.
    class TestPath(type(Path())):
        def lstat(self, *args, **kwargs):
            info = super().lstat(*args, **kwargs)
            mode = info.st_mode if self == sealed.app or sealed.app in self.parents else info.st_mode & ~0o022
            return SimpleNamespace(st_uid=1000 if wrong_owner and self == wrong_owner else 0, st_mode=mode)
    monkeypatch.setattr(sys, 'argv', ['reader', COMMIT, str(sealed.source), str(sealed.output), str(sealed.base)])
    exec(compile(code, 'prepare_cached_freeze', 'exec'), {'Path': TestPath})


def test_cached_freeze_is_copied_byte_exact_without_importing_app(monkeypatch, sealed):
    reader(monkeypatch, sealed)
    assert sealed.output.read_bytes() == sealed.freeze


def test_cached_freeze_rejects_untrusted_owner(monkeypatch, sealed):
    with pytest.raises(SystemExit, match='caminho inseguro'):
        reader(monkeypatch, sealed, wrong_owner=sealed.app / '.telz-python-freeze.txt')


def test_cached_freeze_rejects_source_requirement_drift(monkeypatch, sealed):
    (sealed.source / 'backend/requirements.txt').write_text('Example>=9\n')
    with pytest.raises(SystemExit, match='fonte Git aprovada'):
        reader(monkeypatch, sealed)


def test_cached_freeze_rejects_content_tampering(monkeypatch, sealed):
    path = sealed.app / '.telz-python-freeze.txt'
    path.chmod(0o644)
    path.write_bytes(b'Example==9.0\n')
    path.chmod(0o444)
    with pytest.raises(SystemExit, match='digest do freeze cache divergiu'):
        reader(monkeypatch, sealed)


def test_cached_freeze_rejects_unfinished_build(monkeypatch, sealed):
    (sealed.app.parent / '.building').touch()
    with pytest.raises(SystemExit, match='ainda esta em build'):
        reader(monkeypatch, sealed)


def test_new_commit_without_cache_leaves_fresh_resolution_enabled(monkeypatch, sealed, tmp_path):
    fresh = SimpleNamespace(**{**vars(sealed), 'base': tmp_path / 'not-built'})
    with pytest.raises(SystemExit) as exited:
        reader(monkeypatch, fresh)
    assert exited.value.code == 0 and not fresh.output.exists()


def test_cached_freeze_rejects_other_content_tampering(monkeypatch, sealed):
    path = sealed.app / '.telz-build-metadata.json'
    path.chmod(0o644)
    build = json.loads(path.read_text())
    build['unexpected'] = 'changed-after-seal'
    path.write_text(json.dumps(build))
    path.chmod(0o444)
    with pytest.raises(SystemExit, match='conteudo do cache freeze divergiu'):
        reader(monkeypatch, sealed)


def test_even_self_consistent_cache_cannot_supply_pip_options(monkeypatch, sealed):
    def rewrite(path, data):
        path.chmod(0o644)
        path.write_bytes(data)
        path.chmod(0o444)
    pins = b'--extra-index-url=https://untrusted.example.com\n'
    rewrite(sealed.app / '.telz-python-freeze.txt', pins)
    manifest_path = sealed.app / '.telz-release.json'
    build_path = sealed.app / '.telz-build-metadata.json'
    manifest, build = json.loads(manifest_path.read_text()), json.loads(build_path.read_text())
    manifest['python_freeze_sha256'] = build['python_freeze_sha256'] = hashlib.sha256(pins).hexdigest()
    rewrite(build_path, json.dumps(build).encode())
    manifest['content_sha256'] = content_digest(sealed.app)
    rewrite(manifest_path, json.dumps(manifest).encode())
    with pytest.raises(SystemExit, match='somente pins de pacote'):
        reader(monkeypatch, sealed)


def test_origin_constraints_and_downloads_are_per_commit_and_bundle_pins_are_sealed():
    source = (ROOT / 'scripts/deploy-telz-from-origin.sh').read_text()
    assert '"${TARGET_CONSTRAINTS[@]}"' in source and '"${PREVIOUS_CONSTRAINTS[@]}"' in source
    downloads = [line for line in source.splitlines() if line.startswith('run_as_builder python3.12 -m pip download')]
    assert len(downloads) == 3
    assert all(not ('target-freeze' in line and 'previous-freeze' in line) for line in downloads)
    tooling = [line for line in downloads if 'pip==25.1.1' in line]
    assert len(tooling) == 1 and 'pytest==8.3.5' in tooling[0] and 'httpx==0.28.1' in tooling[0]
    assert '-freeze.txt' not in tooling[0]
    assert all('httpx==' not in line and 'pytest==' not in line and 'pip==' not in line
               for line in downloads if '-freeze.txt' in line)
    assert 'python-freezes/$TARGET_COMMIT.txt' in source and 'python-freezes/$PREVIOUS_COMMIT.txt' in source
    assert '-- wheelhouse pnpm-store python-freezes .telz-dependencies.json' in source
    assert 'mesmo commit produziu freezes diferentes' in source


def test_resolver_cannot_change_cached_freeze_bytes(monkeypatch, tmp_path):
    source = (ROOT / 'scripts/deploy-telz-from-origin.sh').read_text()
    marker = '/usr/bin/python3 - "$DEPENDENCIES/target-report.json"'
    code = re.search(r"<<'PY'\n(.*?)\nPY", source.split(marker, 1)[1], re.S).group(1)
    report = tmp_path / 'report.json'
    report.write_text(json.dumps({'install': [{'metadata': {'name': 'Example', 'version': '9.0'}}]}))
    cached = tmp_path / 'cached.txt'
    cached.write_bytes(b'Example==1.0\n')
    out = tmp_path / 'out.txt'
    monkeypatch.setattr(sys, 'argv', ['validator', str(report), str(out), str(report), str(out), str(cached), str(cached)])
    with pytest.raises(SystemExit, match='divergiu do freeze selado'):
        exec(compile(code, 'report_freeze', 'exec'), {})
    assert not out.exists()
