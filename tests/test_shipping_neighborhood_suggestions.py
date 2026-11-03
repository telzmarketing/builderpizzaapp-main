from types import SimpleNamespace

from backend.models.shipping_v2 import ShippingNeighborhood
from backend.services.delivery_service import DeliveryService
from backend.services.shipping_service import ShippingService


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        import json
        return json.dumps(self.payload).encode()


def test_delivery_geocoder_returns_limited_neighborhood_suggestions(monkeypatch):
    payload = [
        {
            "display_name": "Centro, São Paulo, Brasil",
            "lat": "-23.55",
            "lon": "-46.63",
            "address": {"neighbourhood": "Centro", "city": "São Paulo"},
        },
        {
            "display_name": "Centro, São Paulo, Brasil",
            "lat": "-23.55",
            "lon": "-46.63",
            "address": {"neighbourhood": "Centro", "city": "São Paulo"},
        },
        {
            "display_name": "Moema, São Paulo, Brasil",
            "lat": "-23.60",
            "lon": "-46.66",
            "address": {"suburb": "Moema", "city": "São Paulo"},
        },
        {
            "display_name": "Centro, Campinas, Brasil",
            "lat": "-22.90",
            "lon": "-47.06",
            "address": {"neighbourhood": "Centro", "city": "Campinas"},
        },
    ]
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *_args, **_kwargs: _Response(payload),
    )
    service = DeliveryService.__new__(DeliveryService)
    service._wave7_enabled = False
    service._tenant_context = None
    service._tenant_id = None

    result = service.search_neighborhoods("São Paulo", term="", limit=2)

    assert result == [
        {
            "display_name": "Centro, São Paulo, Brasil",
            "neighborhood": "Centro",
            "city": "São Paulo",
            "lat": -23.55,
            "lng": -46.63,
        },
        {
            "display_name": "Moema, São Paulo, Brasil",
            "neighborhood": "Moema",
            "city": "São Paulo",
            "lat": -23.6,
            "lng": -46.66,
        },
    ]


def test_delivery_geocoder_returns_empty_list_when_nominatim_fails(monkeypatch):
    def fail(*_args, **_kwargs):
        raise TimeoutError("nominatim unavailable")

    monkeypatch.setattr("urllib.request.urlopen", fail)
    service = DeliveryService.__new__(DeliveryService)
    service._wave7_enabled = False
    service._tenant_context = None
    service._tenant_id = None

    assert service.search_neighborhoods("São Paulo") == []


def test_shipping_service_delegates_suggestions_with_tenant_context(monkeypatch):
    context = SimpleNamespace(tenant_id="tenant-a")
    service = ShippingService.__new__(ShippingService)
    service._db = SimpleNamespace()
    service._tenant_context = context
    service._tenant_enabled = True

    observed = {}

    class FakeDeliveryService:
        def __init__(self, db, tenant_id=None, tenant_context=None):
            observed["db"] = db
            observed["tenant_id"] = tenant_id
            observed["tenant_context"] = tenant_context

        def search_neighborhoods(self, **kwargs):
            observed["kwargs"] = kwargs
            return [{
                "display_name": "Centro, São Paulo, Brasil",
                "neighborhood": "Centro",
                "city": "São Paulo",
                "lat": -23.55,
                "lng": -46.63,
            }]

    monkeypatch.setattr("backend.services.delivery_service.DeliveryService", FakeDeliveryService)

    result = service.suggest_neighborhoods("São Paulo", "cent", 5)

    assert result[0].neighborhood == "Centro"
    assert observed["tenant_id"] == "tenant-a"
    assert observed["tenant_context"] is context
    assert observed["kwargs"] == {"city": "São Paulo", "term": "cent", "limit": 5}
