from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_upload_static_mount_is_disabled_when_namespace_rollout_is_enabled():
    source = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")

    assert "if not settings.TENANT_UPLOAD_NAMESPACE_ENABLED:" in source
    assert 'app.mount("/uploads", CachedStaticFiles(directory="uploads", html=False), name="uploads")' in source
    assert 'app.mount("/api/uploads", CachedStaticFiles(directory="uploads", html=False), name="api-uploads")' in source


def test_tenant_upload_reads_require_public_tenant_context_when_enabled():
    source = (ROOT / "backend" / "routes" / "upload_optimized.py").read_text(encoding="utf-8")

    assert "def _enforce_tenant_upload_read(request: Request, db: Session, path: str):" in source
    assert "TENANT_UPLOAD_NAMESPACE_ENABLED" in source
    assert "TenantUploadService(db).require_read_access(request, clean)" in source
    assert '".." in clean.split("/")' in source
    assert "@router.get(\"/{path:path}\")" in source


def test_upload_ownership_migration_never_assigns_legacy_media_to_default():
    source = (ROOT / "backend" / "migrations" / "versions" / "20261004_tenant_upload_ownership_contract.py").read_text(encoding="utf-8")

    assert "tenant_upload_assets" in source
    assert "tenant_upload_legacy_references" in source
    assert "does not create an asset" in source
    assert "tenant-legacy-default" not in source
