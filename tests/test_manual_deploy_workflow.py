from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_manual_deploy_workflow_packages_only_verified_non_secret_artifacts():
    workflow = (ROOT / ".github/workflows/prepare-manual-deploy.yml").read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "previous_commit:" in workflow
    assert "git merge-base --is-ancestor" in workflow
    assert "operation-bundle.tar.gz" in workflow
    assert "target-source.tar.gz" in workflow
    assert "previous-source.tar.gz" in workflow
    assert "dependency-bundle.tar.gz" in workflow
    assert "telz-manual-manifest.json" in workflow
    assert "schema_version" in workflow
    assert "target_commit" in workflow
    assert "previous_commit" in workflow
    assert "alembic_target" in workflow
    assert "public_health_url" in workflow
    assert "sha256" in workflow
    assert "secrets." not in workflow
    assert "ssh " not in workflow
    assert "scp " not in workflow
    assert "retention-days: 14" in workflow
