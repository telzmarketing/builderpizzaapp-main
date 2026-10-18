"""Schema checks use all runtime models and a database built only by Alembic."""
import importlib
import os
import pkgutil
from datetime import datetime, timezone
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session


@pytest.fixture
def runtime_db():
    url = os.environ.get("RUNTIME_SCHEMA_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Requires an explicitly selected, fully migrated test PostgreSQL database")
    import backend.models
    for module in pkgutil.iter_modules(backend.models.__path__):
        importlib.import_module("backend.models." + module.name)
    from backend.main import app  # noqa: F401

    engine = sa.create_engine(url, connect_args={"connect_timeout": 5})
    assert engine.dialect.name == "postgresql"
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                with Session(bind=connection, join_transaction_mode="create_savepoint") as db:
                    yield db
            finally:
                transaction.rollback()
    finally:
        engine.dispose()


def test_all_runtime_models_have_queryable_columns_after_alembic(runtime_db):
    from backend.database import Base

    connection = runtime_db.connection()
    columns = sa.inspect(connection).get_multi_columns(schema="public")
    assert len(Base.metadata.tables) >= 200, "Runtime routes/models were not fully imported"
    missing = []
    for name, table in sorted(Base.metadata.tables.items()):
        actual = {column["name"] for column in columns.get(("public", name), [])}
        absent = set(table.columns.keys()) - actual
        if absent:
            missing.append(f"{name}: {', '.join(sorted(absent))}")
    assert not missing, "Runtime columns missing after Alembic:\n" + "\n".join(missing)

    # LIMIT 0 validates the whole projection without reading any business data.
    for _, table in sorted(Base.metadata.tables.items()):
        connection.execute(sa.select(table).limit(0)).close()


@pytest.mark.parametrize("enabled", [False, True])
def test_shipping_reads_backfilled_singleton_by_owner(runtime_db, monkeypatch, enabled):
    from backend.core.tenant_context import TenantContext, TenantSource
    from backend.models.shipping_v2 import ShippingConfig
    from backend.services import shipping_service

    monkeypatch.setattr(shipping_service, "operations_enforcement_enabled", lambda: enabled)
    monkeypatch.setattr(shipping_service, "wave7_orm_enabled", lambda: False)
    tenant_id = "tenant-legacy-default"
    existing = runtime_db.query(ShippingConfig).filter_by(tenant_id=tenant_id).one_or_none()
    if existing is None:
        existing = ShippingConfig(id="default", tenant_id=tenant_id)
        runtime_db.add(existing)
        runtime_db.commit()
    original_id = existing.id
    context = TenantContext(tenant_id=tenant_id, source=TenantSource.JOB) if enabled else None
    result = shipping_service.ShippingService(runtime_db, context).get_config()
    assert result.id == original_id
    assert result.tenant_id == tenant_id
    assert runtime_db.query(ShippingConfig).filter_by(tenant_id=tenant_id).count() == 1


@pytest.mark.parametrize("enabled", [False, True])
def test_gateway_scheduler_reads_backfilled_singleton_by_owner(runtime_db, monkeypatch, enabled):
    from backend.core.tenant_context import TenantContext, TenantSource
    from backend.models.whatsapp_gateway import WhatsAppGatewaySchedulerSettings
    from backend.services import whatsapp_gateway_service

    monkeypatch.setattr(whatsapp_gateway_service, "wave6_tenant_orm_enabled", lambda: enabled)
    tenant_id = "tenant-legacy-default"
    existing = runtime_db.query(WhatsAppGatewaySchedulerSettings).filter_by(tenant_id=tenant_id).one_or_none()
    if existing is None:
        existing = WhatsAppGatewaySchedulerSettings(id="default", tenant_id=tenant_id, company_id="default")
        runtime_db.add(existing)
        runtime_db.commit()
    original_id = existing.id
    context = TenantContext(tenant_id=tenant_id, source=TenantSource.JOB) if enabled else None
    result = whatsapp_gateway_service.WhatsAppGatewayService(runtime_db, context).get_scheduler_settings()
    assert result.id == original_id
    assert result.tenant_id == tenant_id
    assert runtime_db.query(WhatsAppGatewaySchedulerSettings).filter_by(tenant_id=tenant_id).count() == 1


def test_whatsapp_config_upsert_uses_the_tenant_unique_index(runtime_db):
    from backend.routes.marketing import _set_whatsapp_config_status

    # The migrated tenant has either the historic row or its first configuration.
    # Both calls must work with the partial UNIQUE index created by Alembic.
    tenant_id = "tenant-legacy-default"
    _set_whatsapp_config_status(runtime_db, tenant_id, "connected", datetime.now(timezone.utc))
    _set_whatsapp_config_status(runtime_db, tenant_id, "disconnected", datetime.now(timezone.utc))
    rows = runtime_db.execute(sa.text(
        "SELECT status FROM whatsapp_config WHERE tenant_id = :tenant"
    ), {"tenant": tenant_id}).all()
    assert rows == [("disconnected",)]


@pytest.mark.parametrize("kind", ["shipping", "gateway"])
def test_singleton_creation_and_custom_ids_remain_isolated(runtime_db, monkeypatch, kind):
    from backend.core.tenant_context import TenantContext, TenantSource
    from backend.models.tenant import Tenant
    from backend.models.shipping_v2 import ShippingConfig
    from backend.models.whatsapp_gateway import WhatsAppGatewaySchedulerSettings
    from backend.services import shipping_service, whatsapp_gateway_service

    ids = ["runtime-" + uuid4().hex for _ in range(2)]
    for tenant in ids:
        runtime_db.add(Tenant(id=tenant, slug=tenant, name="Runtime contract test"))
    runtime_db.flush()
    monkeypatch.setattr(shipping_service, "operations_enforcement_enabled", lambda: True)
    monkeypatch.setattr(shipping_service, "wave7_orm_enabled", lambda: False)
    monkeypatch.setattr(whatsapp_gateway_service, "wave6_tenant_orm_enabled", lambda: True)
    model = ShippingConfig if kind == "shipping" else WhatsAppGatewaySchedulerSettings
    custom_id = "custom-" + uuid4().hex
    runtime_db.add(model(id=custom_id, tenant_id=ids[1]))
    runtime_db.commit()

    def owned(tenant):
        context = TenantContext(tenant_id=tenant, source=TenantSource.JOB)
        if kind == "shipping":
            return shipping_service.ShippingService(runtime_db, context).get_config()
        return whatsapp_gateway_service.WhatsAppGatewayService(runtime_db, context).get_scheduler_settings()

    assert owned(ids[0]).tenant_id == ids[0]
    assert owned(ids[1]).id == custom_id
    assert owned(ids[1]).tenant_id == ids[1]
    assert owned(ids[0]).id != custom_id
    assert runtime_db.query(model).filter(model.tenant_id.in_(ids)).count() == 2


@pytest.mark.parametrize("kind", ["shipping", "gateway"])
def test_enforced_singletons_require_trusted_context(runtime_db, monkeypatch, kind):
    from backend.core.tenant_context import TenantContextMissing
    from backend.services import shipping_service, whatsapp_gateway_service

    monkeypatch.setattr(shipping_service, "operations_enforcement_enabled", lambda: True)
    monkeypatch.setattr(shipping_service, "wave7_orm_enabled", lambda: False)
    monkeypatch.setattr(whatsapp_gateway_service, "wave6_tenant_orm_enabled", lambda: True)
    with pytest.raises(TenantContextMissing):
        if kind == "shipping":
            shipping_service.ShippingService(runtime_db).get_config()
        else:
            whatsapp_gateway_service.WhatsAppGatewayService(runtime_db).get_scheduler_settings()
