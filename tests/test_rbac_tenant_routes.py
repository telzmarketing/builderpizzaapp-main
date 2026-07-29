import ast
from pathlib import Path


ROOT = Path(__file__).parents[1]
ROUTE = ROOT / "backend/routes/rbac.py"
TENANT_OWNED_MODELS = {"Role", "RolePermission", "UserPermission", "AdminAuditLog"}


def test_every_tenant_owned_rbac_constructor_sets_tenant_id():
    tree = ast.parse(ROUTE.read_text(encoding="utf-8"))
    constructors = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in TENANT_OWNED_MODELS
    ]

    assert constructors
    assert {node.func.id for node in constructors} == TENANT_OWNED_MODELS
    for constructor in constructors:
        assert any(keyword.arg == "tenant_id" for keyword in constructor.keywords), (
            f"{constructor.func.id} sem tenant_id na linha {constructor.lineno}"
        )


def test_rbac_tenant_comes_from_trusted_panel_context_with_legacy_fallback():
    route = ROUTE.read_text(encoding="utf-8")

    assert "resolve_panel_tenant_context(request, db, user)" in route
    assert 'LEGACY_TENANT_ID = "tenant-legacy-default"' in route
    assert "context.tenant_id if context is not None else LEGACY_TENANT_ID" in route
