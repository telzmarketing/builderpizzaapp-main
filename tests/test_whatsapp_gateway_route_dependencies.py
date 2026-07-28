from pathlib import Path


ROUTE = (
    Path(__file__).parents[1]
    / "backend/routes/whatsapp_gateway.py"
)


def test_whatsapp_gateway_uses_fastapi_compatible_tenant_dependency():
    route = ROUTE.read_text(encoding="utf-8")

    assert (
        "from backend.core.tenant_route_context import panel_operation_context"
        in route
    )
    assert "Depends(resolve_panel_tenant_context)" not in route
    assert route.count("Depends(panel_operation_context)") > 0
