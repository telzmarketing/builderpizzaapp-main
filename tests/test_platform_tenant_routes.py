from pathlib import Path
import re


ROOT = Path(__file__).parents[1]


def _function_source(source: str, function_name: str) -> str:
    match = re.search(
        rf"(?ms)^def {re.escape(function_name)}\(.*?(?=^@(?:router|master_router|host_router)\.|\Z)",
        source,
    )
    assert match is not None, f"route function {function_name} is missing"
    return match.group(0)


def test_platform_tenant_routes_require_explicit_platform_permissions():
    route = (ROOT / "backend/routes/platform_tenants.py").read_text(encoding="utf-8")

    assert 'prefix="/admin/platform/tenants"' in route
    assert 'prefix="/admin/platform"' in route

    view_routes = (
        "list_tenants", "tenant_detail", "list_tenant_users", "tenant_security",
        "tenant_usage", "tenant_notes", "list_tenant_modules", "tenant_license",
        "list_domains", "dashboard", "all_domains", "list_plans", "list_modules",
        "list_invoices",
    )
    for function_name in view_routes:
        assert 'require_platform_permission("tenants.view")' in _function_source(route, function_name)

    manage_routes = (
        "create_tenant", "update_tenant", "update_tenant_status", "suspend_tenant",
        "reactivate_tenant", "archive_tenant", "add_tenant_note",
        "create_tenant_user", "update_tenant_user_role", "update_tenant_user_status",
        "block_tenant_user", "reactivate_tenant_user", "reset_tenant_user_password",
        "revoke_tenant_user_sessions",
        "transfer_tenant_ownership",
        "update_tenant_modules", "change_tenant_plan", "tenant_license_action",
        "create_domain", "verify_domain", "activate_domain", "primary_domain",
        "suspend_domain", "remove_domain", "create_plan", "update_plan",
        "create_module", "create_invoice", "register_payment",
    )
    for function_name in manage_routes:
        assert 'require_platform_permission("tenants.manage")' in _function_source(route, function_name)

    assert 'require_platform_permission("audit.view")' in _function_source(route, "audit_logs")
    assert 'require_platform_permission("support.impersonate")' in _function_source(route, "start_support")
    assert 'require_platform_permission("support.impersonate")' in _function_source(route, "end_support")

    # Provisioning and membership rules live in the transactional service, not the route.
    assert "TenantMembership(" not in route
    assert "service.provision(" in route
    assert "service.create_legacy_compatible(" in route
    assert "PlatformMasterService(db).create_domain(" in route
    assert "TenantDomainService(db).create_pending(" not in route
    assert '@host_router.get("/host-surface", response_model=' in route
    assert "resolve_active_tenant_id(" in route


def test_every_platform_route_declares_and_uses_a_pydantic_response_contract():
    import ast

    route = (ROOT / "backend/routes/platform_tenants.py").read_text(encoding="utf-8")
    tree = ast.parse(route)
    route_count = 0
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                continue
            owner = decorator.func.value
            if not isinstance(owner, ast.Name) or owner.id not in {
                "router", "master_router", "host_router",
            }:
                continue
            route_count += 1
            assert any(keyword.arg == "response_model" for keyword in decorator.keywords), (
                f"route {node.name} is missing response_model"
            )
    assert route_count >= 50
    assert "def _success(data):" in route
    assert "from backend.core.response import" not in route


def test_platform_tenant_router_is_registered():
    main = (ROOT / "backend/main.py").read_text(encoding="utf-8")

    assert "from backend.routes import platform_tenants as platform_tenants_routes" in main
    assert 'app.include_router(platform_tenants_routes.router, prefix="/api")' in main
    assert 'app.include_router(platform_tenants_routes.master_router, prefix="/api")' in main
    assert 'app.include_router(platform_tenants_routes.host_router, prefix="/api")' in main
