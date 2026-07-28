import ast
from pathlib import Path


ROOT = Path(__file__).parents[1]
SEED = ROOT / "backend/core/seed.py"
COUPON_MODEL = ROOT / "backend/models/coupon.py"


def test_tenantized_startup_seeds_use_legacy_tenant():
    seed = SEED.read_text(encoding="utf-8")
    module = ast.parse(seed)
    tenantized_models = {
        "MultiFlavorsConfig",
        "Product",
        "Promotion",
        "Coupon",
        "ChatbotSettings",
        "ShippingRule",
        "Role",
        "RolePermission",
    }
    constructors = [
        node
        for node in ast.walk(module)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in tenantized_models
    ]

    assert 'LEGACY_TENANT_ID = "tenant-legacy-default"' in seed
    assert {node.func.id for node in constructors} == tenantized_models
    for constructor in constructors:
        tenant_keyword = next(
            (keyword for keyword in constructor.keywords if keyword.arg == "tenant_id"),
            None,
        )
        assert tenant_keyword is not None
        assert isinstance(tenant_keyword.value, ast.Name)
        assert tenant_keyword.value.id == "LEGACY_TENANT_ID"

    assert "MultiFlavorsConfig.tenant_id == LEGACY_TENANT_ID" in seed


def test_coupon_orm_maps_ancestral_tenant_column_and_pair_index():
    model = COUPON_MODEL.read_text(encoding="utf-8")

    assert "tenant_id = Column(" in model
    assert '"fk_coupons_tenant_id_tenants"' in model
    assert '"uq_coupons_tenant_id_id"' in model
