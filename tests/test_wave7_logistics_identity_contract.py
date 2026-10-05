from pathlib import Path

from backend.models.delivery import Delivery, DeliveryPerson, GeocodeCache, LogisticsSettings


def test_logistics_singletons_and_geocode_use_tenant_owned_identity() -> None:
    assert {column.name for column in LogisticsSettings.__table__.primary_key.columns} == {"tenant_id", "id"}
    assert {column.name for column in GeocodeCache.__table__.primary_key.columns} == {"tenant_id", "id"}


def test_driver_email_and_delivery_order_are_not_global_unique_keys() -> None:
    assert DeliveryPerson.__table__.c.email.unique is not True
    assert Delivery.__table__.c.order_id.unique is not True
    indexes = {index.name for index in DeliveryPerson.__table__.indexes}
    assert "uq_delivery_persons_tenant_email" in indexes
    indexes = {index.name for index in Delivery.__table__.indexes}
    assert "uq_deliveries_tenant_order" in indexes


def test_logistics_delivery_records_require_a_tenant() -> None:
    assert DeliveryPerson.__table__.c.tenant_id.nullable is False
    assert Delivery.__table__.c.tenant_id.nullable is False
    from backend.models.delivery import DeliveryEarning, DeliveryEvent
    assert DeliveryEvent.__table__.c.tenant_id.nullable is False
    assert DeliveryEarning.__table__.c.tenant_id.nullable is False


def test_logistics_identity_migration_fails_closed_and_never_backfills() -> None:
    source = Path("backend/migrations/versions/20261004_wave7_logistics_identity_contract.py").read_text(encoding="utf-8")
    assert "Wave 7 logistica: tenant ownership invalido" in source
    assert "relacionamento entre empresas bloqueia a migracao" in source
    assert "UPDATE " not in source
    assert "INSERT INTO " not in source
    assert "_drop_legacy_single_column_unique(bind, \"deliveries\", \"order_id\")" in source
    assert "_drop_legacy_single_column_unique(bind, \"delivery_persons\", \"email\")" in source
    assert "_drop_legacy_single_column_unique(bind, \"freight_type_configs\", \"freight_type\")" in source
    assert "op.alter_column(table, \"tenant_id\", existing_type=sa.String(), nullable=False" in source
    assert "_has_composite_fk" in source
