"""Finance settings keep the existing projection switches tenant-safe and typed."""

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.database import Base
from backend.models.gestao import GestaoModuleSettings
from backend.models.tenant import Tenant
from backend.services.gestao_service import GestaoInvalidFinanceSetting, GestaoService
from backend.schemas.gestao import GestaoModuleSettingsUpdate


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[Tenant.__table__, GestaoModuleSettings.__table__])
    with Session(engine) as session:
        yield session
    engine.dispose()


def test_finance_settings_update_preserves_defaults_and_changes_projection_switch(db):
    service = GestaoService(db, "tenant-a")
    result = service.update_settings(
        "finance",
        GestaoModuleSettingsUpdate(settings={"auto_create_receivables": False}),
    )

    assert result["settings"]["auto_create_receivables"] is False
    assert result["settings"]["dre_enabled"] is True
    assert result["settings"]["auto_create_payables_from_purchases"] is True


def test_finance_settings_accept_tenant_owned_account_ids(db):
    result = GestaoService(db, "tenant-a").update_settings(
        "finance",
        GestaoModuleSettingsUpdate(settings={
            "default_receivable_account_id": "fin-acc-receivable",
            "default_payable_account_id": None,
        }),
    )

    assert result["settings"]["default_receivable_account_id"] == "fin-acc-receivable"
    assert result["settings"]["default_payable_account_id"] is None


@pytest.mark.parametrize("patch", [
    {"auto_create_receivables": "false"},
    {"unknown_switch": True},
    {"default_receivable_account_id": 123},
])
def test_finance_settings_reject_unknown_or_non_boolean_switches(db, patch):
    service = GestaoService(db, "tenant-a")

    with pytest.raises(GestaoInvalidFinanceSetting):
        service.update_settings("finance", GestaoModuleSettingsUpdate(settings=patch))


def test_finance_settings_are_isolated_between_tenants(db):
    service_a = GestaoService(db, "tenant-a")
    service_b = GestaoService(db, "tenant-b")
    service_a.update_settings("finance", GestaoModuleSettingsUpdate(settings={"dre_enabled": False}))

    assert service_b.list_settings()[2]["settings"]["dre_enabled"] is True
    stored = db.query(GestaoModuleSettings).filter_by(tenant_id="tenant-a", module_key="finance").one()
    assert json.loads(stored.settings_json)["dre_enabled"] is False
