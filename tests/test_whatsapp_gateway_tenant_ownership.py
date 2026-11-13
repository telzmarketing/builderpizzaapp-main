from backend.core.tenant_context import TenantContext, TenantSource, trusted_process_context
from backend.schemas.whatsapp_gateway import WhatsAppGatewayInstanceCreate
from backend.services import whatsapp_gateway_service
from backend.services.whatsapp_gateway_provider import WhatsAppProviderResult


class FakeSession:
    def __init__(self):
        self.added = []

    def add(self, value):
        self.added.append(value)

    def flush(self):
        return None


class FakeProvider:
    def create_instance(self, *, instance_id, name):
        return WhatsAppProviderResult(ok=True, status="created", message="ok")


def test_create_instance_uses_legacy_owner_when_wave6_disabled(monkeypatch):
    monkeypatch.setattr(whatsapp_gateway_service, "wave6_tenant_orm_enabled", lambda: False)
    service = whatsapp_gateway_service.WhatsAppGatewayService(FakeSession())
    monkeypatch.setattr(service, "_provider", lambda _provider: FakeProvider())

    instance = service.create_instance(WhatsAppGatewayInstanceCreate(name="Principal"))

    assert instance.tenant_id == "tenant-legacy-default"


def test_create_instance_assigns_context_tenant_when_wave6_enabled(monkeypatch):
    monkeypatch.setattr(whatsapp_gateway_service, "wave6_tenant_orm_enabled", lambda: True)
    context = trusted_process_context("tenant-a", source=TenantSource.JOB)
    service = whatsapp_gateway_service.WhatsAppGatewayService(FakeSession(), context)
    monkeypatch.setattr(service, "_provider", lambda _provider: FakeProvider())

    instance = service.create_instance(WhatsAppGatewayInstanceCreate(name="Principal"))

    assert instance.tenant_id == "tenant-a"


def test_create_instance_assigns_panel_context_tenant_when_wave6_disabled(monkeypatch):
    monkeypatch.setattr(whatsapp_gateway_service, "wave6_tenant_orm_enabled", lambda: False)
    context = TenantContext(
        tenant_id="tenant-panel",
        source=TenantSource.PANEL,
        actor_id="admin-a",
        membership_id="membership-a",
    )
    service = whatsapp_gateway_service.WhatsAppGatewayService(FakeSession(), context)
    monkeypatch.setattr(service, "_provider", lambda _provider: FakeProvider())

    instance = service.create_instance(WhatsAppGatewayInstanceCreate(name="Painel"))

    assert service._tenant_enabled is True
    assert instance.tenant_id == "tenant-panel"
