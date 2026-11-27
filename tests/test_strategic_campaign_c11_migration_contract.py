"""C11 database contract parity and tenant-isolation checks."""

import importlib.util
from io import StringIO
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import CheckConstraint, create_engine, inspect
from sqlalchemy.dialects import postgresql, sqlite

import backend.main  # noqa: F401 - load the complete SQLAlchemy registry
from backend.database import Base
from backend.models.order import Order, OrderCommercialGroup, OrderItem
from backend.models.strategic_campaign import (
    StrategicCampaign,
    StrategicOffer,
    StrategicOfferComponent,
    StrategicOfferRedemption,
)


def _checks(model) -> dict[str, str]:
    return {
        constraint.name: str(constraint.sqltext)
        for constraint in model.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }


def _foreign_keys(model) -> dict[str, tuple[tuple[str, ...], tuple[str, ...], str | None]]:
    return {
        constraint.name: (
            tuple(element.parent.name for element in constraint.elements),
            tuple(element.target_fullname for element in constraint.elements),
            constraint.ondelete,
        )
        for constraint in model.__table__.foreign_key_constraints
    }


def _migration_sql() -> str:
    path = Path(__file__).resolve().parents[1] / "backend/migrations/versions/20261126_strategic_campaigns_c11.py"
    spec = importlib.util.spec_from_file_location("strategic_campaigns_c11_migration", path)
    migration = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(migration)
    output = StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql",
        opts={"as_sql": True, "output_buffer": output},
    )
    with Operations.context(context):
        migration.upgrade()
    return output.getvalue()


def test_orm_checks_match_c11_domains_and_entry_channel_is_explicit():
    offer_checks = _checks(StrategicOffer)
    assert set(offer_checks) >= {
        "ck_strategic_offers_reference_type",
        "ck_strategic_offers_pricing_strategy",
        "ck_strategic_offers_composition_revision",
    }
    assert "mixed_subcategories" in offer_checks["ck_strategic_offers_reference_type"]
    assert "fixed_price" in offer_checks["ck_strategic_offers_pricing_strategy"]

    order_checks = _checks(Order)
    assert "legacy_unknown" in order_checks["ck_orders_entry_channel"]
    assert "landing_page" in order_checks["ck_orders_entry_channel"]
    entry_channel = Order.__table__.c.entry_channel
    assert entry_channel.nullable is False
    assert entry_channel.default is None
    assert entry_channel.server_default is None


def test_json_contract_is_sqlite_portable_and_postgresql_jsonb():
    restrictions = StrategicOfferComponent.__table__.c.restrictions.type
    commercial_snapshot = OrderCommercialGroup.__table__.c.commercial_snapshot.type
    assert restrictions.compile(dialect=sqlite.dialect()) == "JSON"
    assert commercial_snapshot.compile(dialect=sqlite.dialect()) == "JSON"
    assert restrictions.compile(dialect=postgresql.dialect()) == "JSONB"
    assert commercial_snapshot.compile(dialect=postgresql.dialect()) == "JSONB"


def test_c11_foreign_keys_are_tenant_safe_and_redemption_lookup_is_indexed():
    group_fks = _foreign_keys(OrderCommercialGroup)
    assert group_fks["fk_order_commercial_groups_campaign"][:2] == (
        ("tenant_id", "strategic_campaign_id"),
        ("strategic_campaigns.tenant_id", "strategic_campaigns.id"),
    )

    item_fks = _foreign_keys(OrderItem)
    assert item_fks["fk_order_items_commercial_group"][:2] == (
        ("tenant_id", "commercial_group_id"),
        ("order_commercial_groups.tenant_id", "order_commercial_groups.id"),
    )
    assert item_fks["fk_order_items_source_subcategory"][:2] == (
        ("tenant_id", "source_subcategory_id"),
        ("product_categories.tenant_id", "product_categories.id"),
    )

    redemption_fks = _foreign_keys(StrategicOfferRedemption)
    assert redemption_fks["fk_strategic_offer_redemptions_group"][:2] == (
        ("tenant_id", "commercial_group_id"),
        ("order_commercial_groups.tenant_id", "order_commercial_groups.id"),
    )
    assert redemption_fks["fk_strategic_offer_redemptions_customer"][:2] == (
        ("tenant_id", "customer_id"),
        ("customers.tenant_id", "customers.id"),
    )
    assert "ix_strategic_offer_redemptions_order_status" in {
        index.name for index in StrategicOfferRedemption.__table__.indexes
    }


def test_c11_metadata_creates_on_sqlite():
    engine = create_engine("sqlite://")
    tables = [
        StrategicCampaign.__table__,
        StrategicOffer.__table__,
        StrategicOfferComponent.__table__,
        Order.__table__,
        OrderCommercialGroup.__table__,
        OrderItem.__table__,
        StrategicOfferRedemption.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    created = set(inspect(engine).get_table_names())
    assert {table.name for table in tables} <= created
    engine.dispose()


def test_postgresql_alembic_sql_preserves_history_and_tenant_contracts():
    sql = _migration_sql()
    assert "UPDATE orders SET entry_channel = 'legacy_unknown'" in sql
    assert "entry_channel VARCHAR(30) NOT NULL" in sql
    assert "DEFAULT 'landing_page'" not in sql
    assert "legacy_unknown" in sql
    assert "restrictions JSONB" in sql
    assert "FOREIGN KEY(tenant_id, commercial_group_id) REFERENCES order_commercial_groups (tenant_id, id)" in sql
    assert "FOREIGN KEY(tenant_id, source_subcategory_id) REFERENCES product_categories (tenant_id, id)" in sql
    assert "FOREIGN KEY(tenant_id, customer_id) REFERENCES customers (tenant_id, id)" in sql
    assert "CREATE INDEX ix_strategic_offer_redemptions_order_status" in sql

