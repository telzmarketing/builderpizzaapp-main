from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_platform_session_route_is_allowlisted_and_protected():
    route = (ROOT / "backend/routes/platform_session.py").read_text(encoding="utf-8")
    assert 'prefix="/admin/platform/session"' in route
    assert '@router.get("", response_model=ApiEnvelope[PlatformSessionOut])' in route
    assert "Depends(require_platform_access())" in route
    assert "current_admin.id" in route
    assert "@router.post" not in route
    assert "@router.patch" not in route
    assert "@router.delete" not in route


def test_platform_session_service_projects_only_roles_and_permissions():
    source = (ROOT / "backend/services/platform_session_service.py").read_text(encoding="utf-8")
    assert "PlatformRole.key, PlatformRole.name" in source
    assert "PlatformPermission.key" in source
    assert ".distinct()" in source
    assert '"user_id"' in source
    for forbidden in ("password", "token", "email", "credentials_json"):
        assert forbidden not in source.lower()
