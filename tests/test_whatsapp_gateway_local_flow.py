"""Local HTTP/SQLite flow; the runtime transport is simulated, never WhatsApp."""
import importlib
import json
import pkgutil
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.models
from backend.config import get_settings
from backend.core.tenant_context import TenantContext, TenantSource
from backend.core.tenant_route_context import panel_operation_context
from backend.core.wave6_tenant_context import bind_wave6_tenant_context, panel_wave6_context
from backend.database import Base, get_db
from backend.models.agente_whatsapp import AgenteWhatsAppChannelSettings, AgenteWhatsAppSession
from backend.models.customer import Customer
from backend.models.tenant import Tenant
from backend.models.whatsapp_gateway import WhatsAppGatewayInstance
from backend.routes import agente_whatsapp, whatsapp_gateway
from backend.routes.admin_auth import get_current_admin
from backend.services.whatsapp_gateway_service import WhatsAppGatewayService


@pytest.fixture(params=[False, True], ids=["rollout-off", "rollout-on"])
def local_flow(request, monkeypatch):
    # Register the same mapper targets as the app, without running app startup,
    # migrations, workers or connecting to a configured database.
    for module in pkgutil.iter_modules(backend.models.__path__):
        importlib.import_module(f"backend.models.{module.name}")
    settings = get_settings()
    monkeypatch.setattr(settings, "MULTI_TENANT_WAVE6_ORM_ENABLED", False)
    monkeypatch.setattr(settings, "WHATSAPP_GATEWAY_EVENT_TOKEN", "local-event-token")
    monkeypatch.setattr(settings, "WHATSAPP_GATEWAY_RUNTIME_TOKEN", "local-runtime-token")
    monkeypatch.setattr(settings, "TENANT_BACKGROUND_CONTEXT_ENABLED", True)

    transport = SimpleNamespace(sent=[], statuses={"instance-a": "connected", "instance-b": "connected"})

    class RuntimeHandler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            self.respond()

        def do_POST(self):
            self.respond()

        def respond(self):
            assert self.headers.get("Authorization") == "Bearer local-runtime-token"
            parts = self.path.split("/")
            instance_id = parts[2]
            data = {"instance_id": instance_id, "status": transport.statuses[instance_id]}
            if self.command == "POST":
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                transport.sent.append({"instance_id": instance_id, **body})
                data.update(status="sent", provider_message_id=f"out-{len(transport.sent)}")
            encoded = json.dumps({"ok": True, "message": "Simulated runtime", "data": data}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    runtime = ThreadingHTTPServer(("127.0.0.1", 0), RuntimeHandler)
    worker = threading.Thread(target=runtime.serve_forever, daemon=True)
    worker.start()
    monkeypatch.setattr(settings, "WHATSAPP_GATEWAY_RUNTIME_URL", f"http://127.0.0.1:{runtime.server_port}")

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    table_names = {
        "tenants", "admin_users", "customers", "customer_channels", "customer_auth", "customer_preferences",
        "whatsapp_gateway_instances", "whatsapp_gateway_logs", "delivery_persons",
        "agente_whatsapp_sessions", "agente_whatsapp_messages", "agente_whatsapp_context",
        "agente_whatsapp_events", "agente_whatsapp_processing_jobs", "agente_whatsapp_outbox",
        "agente_whatsapp_provider_states", "agente_whatsapp_channel_settings",
    }
    # Include only the WhatsApp flow tables; SQLite does not emulate PostgreSQL
    # migrations or concurrency locking.
    Base.metadata.create_all(engine, tables=[Base.metadata.tables[name] for name in table_names])
    # PostgreSQL's partial legacy index becomes unconditional on SQLite.
    # Recreate its intended predicate only inside this disposable database.
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP INDEX uq_tenants_single_legacy")
        connection.exec_driver_sql("CREATE UNIQUE INDEX uq_tenants_single_legacy ON tenants(is_legacy) WHERE is_legacy = 1 AND deleted_at IS NULL")
    db = sessionmaker(bind=engine)()
    for tenant_id in ("tenant-a", "tenant-b"):
        suffix = tenant_id[-1]
        db.add(Tenant(id=tenant_id, name=tenant_id, slug=tenant_id, status="active"))
        db.add(Customer(id=f"customer-{suffix}", tenant_id=tenant_id, name=f"Customer {suffix}",
                        phone="5511999999999", normalized_phone="5511999999999"))
        db.add(WhatsAppGatewayInstance(id=f"instance-{suffix}", tenant_id=tenant_id,
                                      name=f"Gateway {suffix}", provider="baileys", status="connecting"))
        db.add(AgenteWhatsAppChannelSettings(id=f"channel-{suffix}", tenant_id=tenant_id,
                                            active_provider="baileys", whatsapp_gateway_instance_id=f"instance-{suffix}"))
        db.add(AgenteWhatsAppSession(id=f"session-{suffix}", tenant_id=tenant_id,
                                     customer_id=f"customer-{suffix}", phone="5511999999999",
                                     provider="baileys", origin="manual", ai_enabled=False))
    db.commit()
    monkeypatch.setattr(settings, "MULTI_TENANT_WAVE6_ORM_ENABLED", request.param)

    app = FastAPI()
    app.include_router(whatsapp_gateway.router, prefix="/api")
    app.include_router(agente_whatsapp.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_admin] = lambda: SimpleNamespace(id="local-admin")

    def panel_context(http_request: Request):
        context = TenantContext(tenant_id=http_request.headers.get("x-test-tenant", "tenant-a"),
                                source=TenantSource.PANEL, actor_id="local-admin", membership_id="local-membership")
        return bind_wave6_tenant_context(db, context)

    app.dependency_overrides[panel_wave6_context] = panel_context
    app.dependency_overrides[panel_operation_context] = panel_context
    # The newer local WhatsApp dependency delegates to the trusted panel resolver.
    monkeypatch.setattr(agente_whatsapp, "resolve_panel_tenant_context",
                        lambda http_request, _db, _admin: panel_context(http_request))
    try:
        with TestClient(app) as client:
            yield client, db, transport
    finally:
        db.close()
        engine.dispose()
        runtime.shutdown()
        runtime.server_close()
        worker.join(timeout=2)


def test_inbound_list_reply_http_runtime_and_tenant_isolation(local_flow):
    client, db, runtime = local_flow
    payload = {
        "event_type": "message_received", "instance_id": "instance-a", "provider": "baileys",
        "payload": {"tenant_id": "tenant-b"},
        "message": {"id": "inbound-local-a", "phone": "5511999999999",
                    "remote_jid": "5511999999999@s.whatsapp.net", "body": "Ola", "message_type": "text"},
    }
    headers = {"x-whatsapp-gateway-token": "local-event-token"}
    inbound = client.post("/api/whatsapp-gateway/runtime/events", json=payload, headers=headers)
    assert inbound.status_code == 200, inbound.text
    assert inbound.json()["received"] == 1
    duplicate = client.post("/api/whatsapp-gateway/runtime/events", json=payload, headers=headers)
    assert duplicate.json()["duplicates"] == 1

    messages = client.get("/api/agente-whatsapp/sessions/session-a/messages")
    assert messages.status_code == 200, messages.text
    assert [row["body"] for row in messages.json()] == ["Ola"]
    assert client.get("/api/agente-whatsapp/sessions/session-a/messages", headers={"x-test-tenant": "tenant-b"}).status_code == 404
    assert [row["id"] for row in client.get("/api/agente-whatsapp/sessions").json()] == ["session-a"]
    assert client.get("/api/agente-whatsapp/sessions/session-b/messages", headers={"x-test-tenant": "tenant-b"}).json() == []

    assumed = client.patch("/api/agente-whatsapp/sessions/session-a", json={"status": "human", "ai_enabled": False})
    assert assumed.status_code == 200, assumed.text
    # A channel change applies to new conversations. Existing Gateway
    # conversations and already recorded messages keep their own provider.
    switched = client.put("/api/agente-whatsapp/channel/settings", json={"active_provider": "official"})
    assert switched.status_code == 200, switched.text
    reply = client.post("/api/agente-whatsapp/sessions/session-a/messages", json={
        "direction": "outbound", "sender_type": "human", "provider": "baileys",
        "message_type": "text", "body": "Boa noite!", "provider_status": "queued",
    })
    assert reply.status_code == 201, reply.text
    result = client.post("/api/agente-whatsapp/outbox/process", json={"limit": 20})
    assert result.status_code == 200, result.text
    assert result.json()["sent"] == 1, result.text
    assert runtime.sent == [{"instance_id": "instance-a", "phone": "5511999999999", "text": "Boa noite!"}]
    final = client.get("/api/agente-whatsapp/sessions/session-a/messages").json()
    assert final[-1]["provider_message_id"] == "out-1"
    assert final[-1]["provider_status"] == "sent"
    client.post("/api/agente-whatsapp/outbox/process", json={"limit": 20})
    assert len(runtime.sent) == 1


def test_runtime_callback_requires_token_and_known_instance(local_flow):
    client, _db, runtime = local_flow
    payload = {"event_type": "message_received", "instance_id": "missing", "message": {"id": "x"}}
    assert client.post("/api/whatsapp-gateway/runtime/events", json=payload).status_code == 401
    response = client.post("/api/whatsapp-gateway/runtime/events", json=payload,
                           headers={"x-whatsapp-gateway-token": "local-event-token"})
    assert response.status_code == 404
    assert runtime.sent == []


def test_channel_and_dispatch_reject_foreign_gateway(local_flow):
    client, db, runtime = local_flow
    response = client.put("/api/agente-whatsapp/channel/settings", json={
        "active_provider": "baileys", "whatsapp_gateway_instance_id": "instance-b",
    })
    assert response.status_code == 404
    context = TenantContext(tenant_id="tenant-a", source=TenantSource.JOB)
    result = WhatsAppGatewayService(db, context).send_text_message(
        instance_id="instance-b", phone="5511999999999", text="Should not send",
    )
    assert result.ok is False
    assert runtime.sent == []
