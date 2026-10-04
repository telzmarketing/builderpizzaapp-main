from backend.core.wave6_tenant_orm import (
    SCOPED_UNIQUES,
    WAVE6_TABLES,
    unsafe_wave6_statement_reason,
    wave6_tenant_column,
    wave6_tenant_orm_enabled,
)


def test_wave6_inventory_and_scoped_uniques_are_complete():
    assert len(WAVE6_TABLES) == 90
    assert len(SCOPED_UNIQUES) == 25
    assert set(SCOPED_UNIQUES).issubset(WAVE6_TABLES)


def test_wave6_runtime_opt_in_defaults_off(monkeypatch):
    from backend.config import get_settings

    monkeypatch.delenv("MULTI_TENANT_WAVE6_ORM_ENABLED", raising=False)
    get_settings.cache_clear()
    assert wave6_tenant_orm_enabled() is False
    monkeypatch.setenv("MULTI_TENANT_WAVE6_ORM_ENABLED", "true")
    get_settings.cache_clear()
    assert wave6_tenant_orm_enabled() is True
    get_settings.cache_clear()


def test_wave6_column_is_nullable_without_legacy_default():
    column = wave6_tenant_column("crm_cards")
    assert column.nullable is True
    assert column.default is None
    assert column.server_default is None
    assert next(iter(column.foreign_keys)).name == "fk_crm_cards_tenant"


def test_wave6_model_metadata_uses_migration_constraint_names():
    from backend.models.crm import CustomerAIProfile

    table = CustomerAIProfile.__table__
    index_names = {index.name for index in table.indexes}
    fk_names = {constraint.name for constraint in table.foreign_key_constraints}
    assert "fk_customer_ai_profiles_tenant" in fk_names
    assert "uq_customer_ai_profiles_tenant_id_id" in index_names
    assert "uq_mt_customer_ai_profile_customer" in index_names


def test_wave6_statement_guard_detects_unscoped_table_access():
    assert unsafe_wave6_statement_reason("SELECT * FROM marketing_campaigns") == "marketing_campaigns"
    assert unsafe_wave6_statement_reason("UPDATE crm_cards SET title = :title") == "crm_cards"
    assert unsafe_wave6_statement_reason("DELETE FROM whatsapp_messages WHERE id = :id") == "whatsapp_messages"


def test_wave6_statement_guard_allows_explicit_tenant_predicate():
    assert unsafe_wave6_statement_reason(
        "SELECT * FROM marketing_campaigns WHERE tenant_id = :tenant_id"
    ) is None
    assert unsafe_wave6_statement_reason(
        "INSERT INTO crm_cards (id, tenant_id, title) VALUES (:id, :tenant_id, :title)"
    ) is None
    assert unsafe_wave6_statement_reason("SELECT * FROM products") is None
