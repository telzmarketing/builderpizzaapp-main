"""Exercise the actual updater validators with separate artifact provenance."""
import hashlib
import json
from pathlib import Path
import re
import stat
import sys
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
COMMIT = '1' * 40
REVISION = '20261014_tenant_domain_ssl'


def embedded_validator(function):
    source = (ROOT / 'scripts/update-telz.sh').read_text(encoding='utf-8')
    section = source.split(function + '() {', 1)[1]
    return re.search(r"<<'PY'\n(.*?)\nPY", section, re.S).group(1)


def execute(monkeypatch, function, arguments):
    if sys.platform == 'win32':
        # These fixtures contain no legacy external symlinks; Unix account lookup
        # must remain unused while exercising the real digest/contract checks.
        monkeypatch.setitem(sys.modules, 'pwd', SimpleNamespace(getpwnam=lambda name: pytest.fail('unexpected legacy link')))
    monkeypatch.setattr(sys, 'argv', ['validator', *map(str, arguments)])
    exec(compile(embedded_validator(function), function, 'exec'), {})


def content_digest(root):
    digest = hashlib.sha256()
    for candidate in sorted(root.rglob('*'), key=lambda item: item.relative_to(root).as_posix()):
        relative = candidate.relative_to(root).as_posix()
        if relative == '.telz-release.json':
            continue
        info = candidate.lstat()
        kind, payload = ('d', b'') if stat.S_ISDIR(info.st_mode) else ('f', candidate.read_bytes())
        digest.update(f'{kind}\0{relative}\0{stat.S_IMODE(info.st_mode):04o}\0'.encode())
        digest.update(hashlib.sha256(payload).digest())
    return digest.hexdigest()


@pytest.fixture
def release(tmp_path):
    app = tmp_path / 'app'
    (app / 'backend').mkdir(parents=True)
    (app / 'backend/requirements.txt').write_text('example==1.0\n')
    (app / 'pnpm-lock.yaml').write_text('lockfileVersion: 9\n')
    (app / '.telz-python-freeze.txt').write_text('example==1.0\n')
    public = tmp_path / '.telz-public-build.json'
    public.write_text('{"VITE_API_URL":""}\n')
    hashes = {key: hashlib.sha256(path.read_bytes()).hexdigest() for key, path in {
        'requirements_sha256': app / 'backend/requirements.txt',
        'pnpm_lock_sha256': app / 'pnpm-lock.yaml',
        'python_freeze_sha256': app / '.telz-python-freeze.txt',
    }.items()}
    toolchain = {'python': 'Python 3.12.10', 'pip': '25.1.1', 'node': 'v22.14.0', 'pnpm': '10.14.0'}
    public_hash = hashlib.sha256(public.read_bytes()).hexdigest()
    build = {'schema_version': 1, 'commit': COMMIT, **hashes,
             'public_build_config_sha256': public_hash, 'toolchain': toolchain}
    (app / '.telz-build-metadata.json').write_text(json.dumps(build))
    manifest = {'schema_version': 2, 'status': 'validated', 'git_commit': COMMIT,
                'alembic_revision': REVISION, 'dependency_artifact_sha256': 'a' * 64,
                **hashes, 'public_build_config_sha256': public_hash, 'toolchain': toolchain,
                'cutover': {'mode': 'rollback_safe', 'predecessor_revision': REVISION, 'automatic_rollback': True},
                'content_sha256': content_digest(app)}
    manifest_path = app / '.telz-release.json'
    manifest_path.write_text(json.dumps(manifest))
    metadata = {'schema_version': 1, 'target_commit': COMMIT, 'previous_commit': '2' * 40,
                'commits': {COMMIT: hashes}, 'public_build_config_sha256': public_hash,
                'python': '3.12', 'pip': '25.1.1', 'node': '22', 'pnpm': '10.14.0'}
    metadata_path = tmp_path / '.telz-dependencies.json'
    metadata_path.write_text(json.dumps(metadata))
    return app, manifest_path, metadata_path, public, metadata


def validate_cache(monkeypatch, release):
    app, manifest, metadata, public, _ = release
    execute(monkeypatch, 'validate_release_tree', [app, COMMIT, REVISION, '', 'telz', 'rollback_safe', REVISION, 'false'])
    execute(monkeypatch, 'validate_cached_release_dependencies', [manifest, metadata, public, COMMIT])


def test_repackaged_same_commit_reuses_sealed_release_without_rewriting_provenance(monkeypatch, release):
    _, manifest, metadata_path, _, metadata = release
    original = manifest.read_bytes()
    first_transport = hashlib.sha256(metadata_path.read_bytes()).hexdigest()
    metadata['previous_commit'] = '3' * 40
    metadata['commits']['3' * 40] = {key: 'b' * 64 for key in metadata['commits'][COMMIT]}
    metadata_path.write_text(json.dumps(metadata))
    assert hashlib.sha256(metadata_path.read_bytes()).hexdigest() != first_transport
    validate_cache(monkeypatch, release)
    assert manifest.read_bytes() == original
    assert json.loads(original)['dependency_artifact_sha256'] == 'a' * 64


@pytest.mark.parametrize('key', ['python_freeze_sha256', 'requirements_sha256', 'pnpm_lock_sha256'])
def test_changed_dependency_contract_rejects_cache(monkeypatch, release, key):
    release[4]['commits'][COMMIT][key] = 'f' * 64
    release[2].write_text(json.dumps(release[4]))
    with pytest.raises(SystemExit, match='contrato de dependencias da release cache divergiu'):
        validate_cache(monkeypatch, release)


def test_changed_public_configuration_rejects_cache(monkeypatch, release):
    release[3].write_text('{"VITE_API_URL":"https://other.example.com"}\n')
    with pytest.raises(SystemExit, match='configuracao publica da release cache divergiu'):
        validate_cache(monkeypatch, release)


def test_changed_toolchain_rejects_cache(monkeypatch, release):
    release[4]['pnpm'] = '11.0.0'
    release[2].write_text(json.dumps(release[4]))
    with pytest.raises(SystemExit, match='toolchain da release cache divergiu'):
        validate_cache(monkeypatch, release)


def test_tampered_tree_still_rejected_before_dependency_contract(monkeypatch, release):
    (release[0] / 'backend/requirements.txt').write_text('injected==9.9\n')
    with pytest.raises(SystemExit, match='digest de dependencia da release divergiu'):
        validate_cache(monkeypatch, release)


def test_cutover_policy_is_not_relaxed_for_cached_release(monkeypatch, release):
    with pytest.raises(SystemExit, match='metadata de cutover diverge do target'):
        execute(monkeypatch, 'validate_release_tree', [release[0], COMMIT, REVISION, '', 'telz', 'forward_only', REVISION, 'false'])


def test_new_builds_still_require_exact_requested_artifact(monkeypatch, release):
    with pytest.raises(SystemExit, match='artefato de dependencias diferente'):
        execute(monkeypatch, 'validate_release_tree', [release[0], COMMIT, REVISION, 'b' * 64, 'telz', 'rollback_safe', REVISION, 'false'])
    source = (ROOT / 'scripts/update-telz.sh').read_text(encoding='utf-8')
    assert 'validate_cached_release_dependencies "$release_app" "$release_commit"' in source
    assert source.count('"$DEPENDENCY_ARCHIVE_SHA256" true "$cutover_mode" "$predecessor_revision"') == 1
    assert source.count('"$DEPENDENCY_ARCHIVE_SHA256" false "$cutover_mode" "$predecessor_revision"') == 1


@pytest.mark.parametrize('filename', [
    'scripts/deploy-telz-from-origin.sh',
    'scripts/deploy-telz-artifacts-manually.sh',
    '.github/workflows/deploy.yml',
])
@pytest.mark.parametrize('changed', [False, True])
def test_deploy_postchecks_accept_transport_change_but_reject_contract_change(monkeypatch, release, tmp_path, filename, changed):
    import textwrap
    source = (ROOT / filename).read_text(encoding='utf-8')
    start = source.index('"$ACTIVE_APP/.telz-release.json"')
    block = re.search(r"<<'PY'\n(.*?)\n\s*PY", source[start:], re.S).group(1)
    block = textwrap.dedent(block)
    requested = 'b' * 64
    dependency_root = tmp_path / 'dependency-bundles'
    bundle = dependency_root / requested
    bundle.mkdir(parents=True)
    metadata = release[4]
    if changed:
        metadata['commits'][COMMIT]['python_freeze_sha256'] = 'f' * 64
    (bundle / '.telz-dependencies.json').write_text(json.dumps(metadata))
    block = block.replace("Path('/var/lib/telz/dependency-bundles')", f'Path({str(dependency_root)!r})')
    monkeypatch.setattr(sys, 'argv', ['postcheck', str(release[1]), COMMIT, REVISION, requested])
    original = release[1].read_bytes()
    if changed:
        with pytest.raises(SystemExit, match='contrato de dependencias da release promovida divergiu'):
            exec(compile(block, filename, 'exec'), {})
    else:
        exec(compile(block, filename, 'exec'), {})
    assert release[1].read_bytes() == original
