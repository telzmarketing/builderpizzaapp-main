from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_manual_deploy_is_root_only_and_sealed_by_manifest():
    source = (ROOT / "scripts/deploy-telz-artifacts-manually.sh").read_text(encoding="utf-8")

    assert '[[ "${EUID:-$(id -u)}" -eq 0 ]]' in source
    assert 'MANIFEST_NAME="telz-manual-manifest.json"' in source
    assert 'OPERATION_NAME="operation-bundle.tar.gz"' in source
    assert 'TARGET_NAME="target-source.tar.gz"' in source
    assert 'PREVIOUS_NAME="previous-source.tar.gz"' in source
    assert 'DEPENDENCY_NAME="dependency-bundle.tar.gz"' in source
    assert '"schema_version", "target_commit", "previous_commit", "alembic_target", "public_health_url", "artifacts"' in source
    assert 'hash divergente' in source
    assert 'release ativa nao corresponde ao previous_commit' in source


def test_manual_deploy_rejects_unsafe_bundle_and_uses_hardened_updater_contract():
    source = (ROOT / "scripts/deploy-telz-artifacts-manually.sh").read_text(encoding="utf-8")

    assert 'member.issym() or member.islnk()' in source
    assert 'path.is_absolute() or ".." in path.parts' in source
    assert 'install -m 0400 -o root -g root' in source
    assert 'TELZ_EXPECTED_COMMIT="$TARGET_COMMIT"' in source
    assert 'TELZ_PREVIOUS_COMMIT="$PREVIOUS_COMMIT"' in source
    assert 'TELZ_OPERATION_BUNDLE_DIR="$BUNDLE_STAGE"' in source
    assert 'TELZ_DEPENDENCY_ARCHIVE_SHA256="$DEPENDENCY_SHA"' in source
    assert 'data["public_health_url"] != "https://app.telz.com.br/health"' in source
