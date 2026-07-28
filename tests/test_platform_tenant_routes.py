from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_platform_tenant_routes_require_explicit_platform_permissions():
    route = (ROOT / "backend/routes/platform_tenants.py").read_text(encoding="utf-8")

    assert 'prefix="/admin/platform/tenants"' in route
    assert route.count('require_platform_permission("tenants.view")') == 2
    assert route.count('require_platform_permission("tenants.manage")') == 3
    assert "TenantMembership(" in route
    assert 'role="owner"' in route
    assert "TenantDomainService(db).create_pending(" in route
    assert '@host_router.get("/host-surface")' in route
    assert "resolve_active_tenant_id(" in route


def test_platform_tenant_router_is_registered():
    main = (ROOT / "backend/main.py").read_text(encoding="utf-8")

    assert "from backend.routes import platform_tenants as platform_tenants_routes" in main
    assert 'app.include_router(platform_tenants_routes.router, prefix="/api")' in main
    assert 'app.include_router(platform_tenants_routes.host_router, prefix="/api")' in main
