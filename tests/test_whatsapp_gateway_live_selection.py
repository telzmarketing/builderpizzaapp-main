from types import SimpleNamespace

import backend.models.product_promotion  # noqa: F401 - register ProductPromotion mapper target
import backend.models.salao  # noqa: F401 - register RestaurantTable mapper target
from backend.core.tenant_context import TenantContext, TenantSource
from backend.services import whatsapp_gateway_service
from backend.services.whatsapp_gateway_provider import WhatsAppProviderResult


class SelectionQuery:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *_conditions):
        return self

    def order_by(self, *_ordering):
        return self

    def first(self):
        return self.rows[0] if self.rows else None

    def all(self):
        return list(self.rows)


class SelectionDb:
    def __init__(self, rows):
        self.rows = rows

    def query(self, _model):
        return SelectionQuery(self.rows)


def make_service(rows, statuses):
    for row in rows:
        row.qr_code = None
    service = object.__new__(whatsapp_gateway_service.WhatsAppGatewayService)
    service._db = SelectionDb(rows)
    service._tenant_context = TenantContext(tenant_id="tenant-a", source=TenantSource.JOB)
    service._tenant_enabled = True
    service._scope = lambda query, _model: query
    service.get_instance = lambda instance_id: next((row for row in rows if row.id == instance_id), None)
    service._provider = lambda _provider: SimpleNamespace(
        get_status=lambda *, instance_id: WhatsAppProviderResult(
            ok=statuses[instance_id] == "connected",
            status=statuses[instance_id],
            message=statuses[instance_id],
            data={"status": statuses[instance_id]},
        )
    )
    return service


def test_live_connected_runtime_wins_over_stale_sql_status():
    instance = SimpleNamespace(id="instance-a", tenant_id="tenant-a", provider="baileys", status="connecting")
    service = make_service([instance], {"instance-a": "connected"})

    selected = service._select_send_instance(None)

    assert selected is instance
    assert instance.status == "connected"


def test_live_disconnected_runtime_cannot_be_selected_from_connected_sql_status():
    instance = SimpleNamespace(id="instance-a", tenant_id="tenant-a", provider="baileys", status="connected")
    service = make_service([instance], {"instance-a": "disconnected"})

    assert service._select_send_instance(None) is None
    assert instance.status == "disconnected"


def test_explicit_foreign_instance_does_not_fallback_to_owned_instance():
    foreign = SimpleNamespace(id="foreign", tenant_id="tenant-b", provider="baileys", status="connected")
    owned = SimpleNamespace(id="owned", tenant_id="tenant-a", provider="baileys", status="connected")
    service = make_service([foreign, owned], {"foreign": "connected", "owned": "connected"})

    assert service._select_send_instance("foreign") is None


def test_external_e2e_readiness_is_blocked_without_live_authenticated_instance():
    service = object.__new__(whatsapp_gateway_service.WhatsAppGatewayService)
    instance = SimpleNamespace(id="instance-a", name="Gateway A", status="connecting")
    service.list_instances = lambda: [instance]
    service.installed_baileys_version = lambda: "7.0.0-rc13"
    service._provider = lambda _provider: SimpleNamespace(
        health_check=lambda: WhatsAppProviderResult(
            ok=False, status="runtime_offline", message="Runtime Baileys local indisponivel.", data={}
        ),
        get_status=lambda *, instance_id: WhatsAppProviderResult(
            ok=False, status="runtime_offline", message="Runtime Baileys local indisponivel.", data={"status": "runtime_offline"}
        ),
    )

    result = service.external_e2e_readiness()

    assert result["status"] == "blocked"
    assert result["external_e2e_ready"] is False
    assert {item["code"] for item in result["blockers"]} == {
        "runtime_unavailable", "no_authenticated_connected_instance",
    }


def test_external_e2e_readiness_ignores_stale_connected_sql_status():
    service = object.__new__(whatsapp_gateway_service.WhatsAppGatewayService)
    instance = SimpleNamespace(id="instance-a", name="Gateway A", status="connected")
    service.list_instances = lambda: [instance]
    service.installed_baileys_version = lambda: "7.0.0-rc13"
    service._provider = lambda _provider: SimpleNamespace(
        health_check=lambda: WhatsAppProviderResult(
            ok=True, status="online", message="Runtime online.", data={"status": "online"}
        ),
        get_status=lambda *, instance_id: WhatsAppProviderResult(
            ok=False, status="disconnected", message="Sessao desconectada.", data={"status": "disconnected"}
        ),
    )

    result = service.external_e2e_readiness()

    assert result["external_e2e_ready"] is False
    assert result["instances"][0]["persisted_status"] == "connected"
    assert result["instances"][0]["live_status"] == "disconnected"
