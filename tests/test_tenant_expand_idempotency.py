from pathlib import Path
import ast


VERSIONS = Path(__file__).parents[1] / "backend/migrations/versions"


def _literal_assignment(filename: str, name: str):
    module = ast.parse((VERSIONS / filename).read_text(encoding="utf-8"))
    assignment = next(
        node
        for node in module.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == name for target in node.targets)
    )
    return ast.literal_eval(assignment.value)


def test_late_tenant_expansions_add_tenant_id_idempotently():
    for filename in (
        "20260801_tenant_marketing_crm_whatsapp_expand.py",
        "20260803_tenant_backoffice_async_expand.py",
    ):
        migration = (VERSIONS / filename).read_text(encoding="utf-8")
        assert "ADD COLUMN IF NOT EXISTS tenant_id VARCHAR" in migration


def test_customer_groups_ancestral_tenant_column_is_compatible():
    crm = (
        VERSIONS / "20260501_crm_tags_segments.py"
    ).read_text(encoding="utf-8")
    tenant_expand = (
        VERSIONS / "20260801_tenant_marketing_crm_whatsapp_expand.py"
    ).read_text(encoding="utf-8")

    assert "ALTER TABLE customer_groups ADD COLUMN IF NOT EXISTS tenant_id" in crm
    assert '"customer_groups"' in tenant_expand
    assert "ADD COLUMN IF NOT EXISTS tenant_id VARCHAR" in tenant_expand


def test_coupons_are_tenant_expanded_and_backfilled_before_composite_fks():
    expand_filename = "20260723_tenant_identity_catalog_expand.py"
    backfill_filename = "20260724_tenant_identity_catalog_backfill.py"
    marketing_filename = "20260801_tenant_marketing_crm_whatsapp_expand.py"

    assert "coupons" in _literal_assignment(expand_filename, "TABLES")
    assert "coupons" in _literal_assignment(backfill_filename, "TABLES")

    expand = (VERSIONS / expand_filename).read_text(encoding="utf-8")
    marketing = (VERSIONS / marketing_filename).read_text(encoding="utf-8")
    assert "op.create_index(_idx(table), table, ['tenant_id', 'id'], unique=True)" in expand
    assert (
        '("marketing_campaigns", "coupon_id", "coupons", "SET NULL")'
        in marketing
    )
