from pathlib import Path


VERSIONS = Path(__file__).parents[1] / "backend/migrations/versions"


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
