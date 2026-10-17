"""Exercise BI against the actual Alembic schema, including empty deliveries."""
import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def test_dashboard_on_fully_migrated_postgresql():
    url = os.environ.get("DRIVER_SCHEMA_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Requires the disposable PostgreSQL database migrated by CI")

    # Register all existing model relationships without running app startup.
    from backend.main import app  # noqa: F401
    from backend.core.tenant_context import TenantContext, TenantSource
    from backend.core.wave6_tenant_context import bind_wave6_tenant_context
    from backend.services.business_intelligence_service import BusinessIntelligenceService

    engine = create_engine(url, connect_args={"connect_timeout": 5})
    assert engine.dialect.name == "postgresql"
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                tenant_id = "bi-schema-check-" + uuid4().hex
                with Session(bind=connection, join_transaction_mode="create_savepoint") as db:
                    bind_wave6_tenant_context(
                        db, TenantContext(tenant_id=tenant_id, source=TenantSource.JOB)
                    )
                    dashboard = BusinessIntelligenceService(db, tenant_id).dashboard("30d")
                    assert "kpis" in dashboard
                    assert dashboard["products"] == []
                    assert "generated_at" in dashboard
            finally:
                transaction.rollback()
    finally:
        engine.dispose()
