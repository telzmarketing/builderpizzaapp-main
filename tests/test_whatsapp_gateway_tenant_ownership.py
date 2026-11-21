from types import SimpleNamespace

import backend.models.payment  # noqa: F401 - register the Customer relationship target
import backend.models.product  # noqa: F401 - register the CustomerEvent relationship target
import backend.models.product_promotion  # noqa: F401 - register ProductPromotion mapper target
import backend.models.salao  # noqa: F401 - register RestaurantTable mapper target
from backend.core.tenant_context import TenantContext, TenantSource, trusted_process_context
from backend.routes import whatsapp_gateway as whatsapp_gateway_route
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


class FakeRuntimeQuery:
    def __init__(self, instance):
        self.instance = instance

    def filter(self, *_conditions):
        return self

    def first(self):
        return self.instance


class FakeRuntimeDb:
    def __init__(self, instance):
        self.instance = instance
        self.info = {}
        self.commits = 0

    def query(self, _model):
        return FakeRuntimeQuery(self.instance)

    def commit(self):
        self.commits += 1

    def flush(self):
        return None


class FakeSelectionQuery:
    def __init__(self, instance, instances=None):
        self.instance = instance
        self.instances = list(instances if instances is not None else ([instance] if instance else []))

    def filter(self, *_conditions):
        return self

    def order_by(self, *_ordering):
        return self

    def first(self):
        return self.instance

    def all(self):
        return self.instances


class FakeSelectionDb:
    def __init__(self, instance, instances=None):
        self.instance = instance
        self.instances = instances

    def query(self, _model):
        return FakeSelectionQuery(self.instance, self.instances)


def test_runtime_route_resolves_instance_owner_even_when_rollout_is_disabled(monkeypatch):
    instance = SimpleNamespace(id="instance-a", tenant_id="tenant-a", company_id="company-a")
    db = FakeRuntimeDb(instance)
    captured = {}

    class FakeGatewayService:
        def __init__(self, _db, tenant_context=None):
            captured["context"] = tenant_context

        def process_runtime_event(self, payload):
            captured["payload"] = payload
            return {"ok": True, "received": 1, "duplicates": 0, "ignored": 0, "message": "ok"}

    monkeypatch.setattr(whatsapp_gateway_route, "wave6_tenant_orm_enabled", lambda: False)
    monkeypatch.setattr(
        whatsapp_gateway_route,
        "get_settings",
        lambda: SimpleNamespace(WHATSAPP_GATEWAY_EVENT_TOKEN="secret"),
    )
    monkeypatch.setattr(whatsapp_gateway_route, "_tenant_service", FakeGatewayService)

    body = SimpleNamespace(
        instance_id="instance-a",
        model_dump=lambda: {"instance_id": "instance-a", "event_type": "message_received", "tenant_id": "attacker"},
    )
    result = whatsapp_gateway_route.receive_runtime_event(body, "secret", db)

    assert result["received"] == 1
    assert captured["context"].tenant_id == "tenant-a"
    assert captured["context"].source == TenantSource.WEBHOOK
    assert captured["payload"]["tenant_id"] == "attacker"
    assert db.commits == 1


def test_runtime_event_propagates_persisted_instance_owner_to_agent(monkeypatch):
    instance = SimpleNamespace(id="instance-a", tenant_id="tenant-a", company_id="company-a")
    service = object.__new__(whatsapp_gateway_service.WhatsAppGatewayService)
    service._db = FakeRuntimeDb(instance)
    service._tenant_context = TenantContext(tenant_id="tenant-a", source=TenantSource.WEBHOOK)
    monkeypatch.setattr(service, "get_instance", lambda _instance_id: instance)
    monkeypatch.setattr(service, "add_log", lambda **_kwargs: None)
    monkeypatch.setattr(
        whatsapp_gateway_service,
        "get_settings",
        lambda: SimpleNamespace(TENANT_BACKGROUND_CONTEXT_ENABLED=True),
    )

    captured = {}

    class FakeDriverService:
        def __init__(self, _db):
            pass

        def process_driver_reply(self, _payload):
            return None

    class FakeAgentService:
        def __init__(self, _db, tenant_context=None):
            captured["context"] = tenant_context

        def process_baileys_runtime_event(self, payload):
            captured["payload"] = payload
            return {"received": 1, "duplicates": 0, "ignored": 0}

    monkeypatch.setattr(
        "backend.services.delivery_driver_whatsapp_service.DeliveryDriverWhatsAppService",
        FakeDriverService,
    )
    monkeypatch.setattr(
        "backend.services.agente_whatsapp_service.AgenteWhatsAppService",
        FakeAgentService,
    )

    result = service.process_runtime_event(
        {
            "event_type": "message_received",
            "instance_id": "instance-a",
            "tenant_id": "attacker",
            "_trusted_tenant_id": "attacker",
            "message": {"id": "message-a", "phone": "5511999999999"},
        }
    )

    assert result["received"] == 1
    assert captured["context"].tenant_id == "tenant-a"
    assert captured["context"].source == TenantSource.WEBHOOK
    assert captured["payload"]["_trusted_tenant_id"] == "tenant-a"


def test_unknown_runtime_instance_is_rejected_even_when_rollout_is_disabled(monkeypatch):
    service = object.__new__(whatsapp_gateway_service.WhatsAppGatewayService)
    service._db = FakeRuntimeDb(None)
    service._tenant_context = None
    monkeypatch.setattr(service, "get_instance", lambda _instance_id: None)
    monkeypatch.setattr(service, "add_log", lambda **_kwargs: None)

    result = service.process_runtime_event({
        "event_type": "message_received",
        "instance_id": "unknown",
        "message": {"id": "message-unknown", "phone": "5511999999999"},
    })

    assert result["ok"] is False
    assert result["received"] == 0
    assert result["ignored"] == 1


def test_send_selection_falls_back_to_connected_owned_instance_after_replacement(monkeypatch):
    stale = SimpleNamespace(id="old-instance", tenant_id="tenant-a", provider="baileys", status="disconnected", qr_code=None)
    replacement = SimpleNamespace(id="new-instance", tenant_id="tenant-a", provider="baileys", status="connected", qr_code=None)
    service = object.__new__(whatsapp_gateway_service.WhatsAppGatewayService)
    service._db = FakeSelectionDb(replacement)
    service._tenant_context = TenantContext(tenant_id="tenant-a", source=TenantSource.JOB)
    monkeypatch.setattr(service, "get_instance", lambda _instance_id: stale)
    monkeypatch.setattr(service, "_scope", lambda query, _model: query)
    monkeypatch.setattr(service, "_provider", lambda _provider: SimpleNamespace(
        get_status=lambda **kwargs: WhatsAppProviderResult(
            ok=True, status="disconnected" if kwargs["instance_id"] == stale.id else "connected", message="status",
            data={"status": "disconnected" if kwargs["instance_id"] == stale.id else "connected"}
        )
    ))
    service._tenant_enabled = True

    selected = service._select_send_instance(stale.id)

    assert selected is replacement


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
