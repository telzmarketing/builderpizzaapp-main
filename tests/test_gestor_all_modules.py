from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base
from backend.models.admin import AdminUser
from backend.models.gestor import GestorOperation
from backend.models.membership import TenantMembership
from backend.models.tenant import Tenant
from backend.schemas.gestor import GestorOperationPreviewIn, GestorToolExecuteIn
from backend.services.gestor_service import GestorOperationInvalid, GestorService


@pytest.fixture()
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[
        Tenant.__table__, AdminUser.__table__, TenantMembership.__table__,
        GestorOperation.__table__,
    ])
    session = sessionmaker(bind=engine)()
    tenant_id, admin_id = str(uuid4()), str(uuid4())
    session.add(Tenant(id=tenant_id, slug=f"all-{tenant_id[:8]}", name="Tenant A", status="active"))
    session.add(AdminUser(id=admin_id, email=f"all-{tenant_id[:8]}@test.invalid", name="Admin", password_hash="x", active=True))
    session.add(TenantMembership(id=str(uuid4()), tenant_id=tenant_id, user_id=admin_id, role="owner", status="active"))
    session.commit()
    try:
        yield session, tenant_id, admin_id
    finally:
        session.close()
        engine.dispose()


def test_catalog_contains_all_module_contracts_and_unavailable_reason():
    catalog = {item.name: item for item in GestorService.tool_catalog()}
    assert {
        "gestor.products.catalog", "gestor.crm.summary", "gestor.fiscal.overview",
        "gestor.logistics.summary", "gestor.bi.dashboard", "gestor.inventory.overview",
        "gestor.finance.overview", "gestor.operations.summary",
    } <= catalog.keys()
    for name in ("gestor.products.update_price", "gestor.finance.create_expense",
                 "gestor.inventory.create_manual_entry", "gestor.operations.update_order_status"):
        assert catalog[name].mutates_data is True
        assert catalog[name].requires_confirmation is True
        assert catalog[name].evidence_required
    assert catalog["gestor.crm.create_task"].available is False
    assert "service" in (catalog["gestor.crm.create_task"].unavailable_reason or "").lower()


def test_products_catalog_is_tenant_scoped(db, monkeypatch):
    session, tenant_id, admin_id = db
    monkeypatch.setattr(GestorService, "_execute_products_catalog", lambda self, args: {"tenant_id": self.tenant_id})
    operation, result = GestorService(session, tenant_id, admin_id).execute_tool(
        GestorToolExecuteIn(tool_name="gestor.products.catalog", phone="5511999990000", idempotency_key="catalog-a")
    )
    assert operation.status == "EXECUTED"
    assert result == {"tenant_id": tenant_id}


def test_unknown_tool_is_rejected_without_operation(db):
    session, tenant_id, admin_id = db
    with pytest.raises(GestorOperationInvalid, match="desconhecida"):
        GestorService(session, tenant_id, admin_id).execute_tool(
            GestorToolExecuteIn(tool_name="gestor.sql.query", phone="5511999990000")
        )
    assert session.query(GestorOperation).count() == 0


def test_confirmed_product_write_calls_canonical_handler_once(db, monkeypatch):
    session, tenant_id, admin_id = db
    service = GestorService(session, tenant_id, admin_id)
    operation, token = service.create_operation(GestorOperationPreviewIn(
        channel="gestor", phone="5511999990000", tool_name="gestor.products.update_price",
        risk_level="high", arguments={"product_id": "prod-a", "price": 35},
        preview={"summary": "Atualizar preco da Pizza A", "evidence": {"current_price": 30, "new_price": 35}},
        idempotency_key="price-a", reauthenticated=True,
    ))
    service.confirm_operation(operation.id, token)
    calls = []
    monkeypatch.setattr(GestorService, "_execute_products_update_price", lambda self, args: calls.append(args.product_id) or {"id": args.product_id, "price": args.price})
    executed, result = service.execute_tool(GestorToolExecuteIn(
        operation_id=operation.id, tool_name="gestor.products.update_price", phone="5511999990000",
        arguments={"product_id": "prod-a", "price": 35}, reauthenticated=True,
    ))
    assert calls == ["prod-a"]
    assert executed.status == "EXECUTED"
    assert result == {"id": "prod-a", "price": 35}
