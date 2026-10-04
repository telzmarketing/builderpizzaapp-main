"""Contract checks for public Agente WhatsApp callbacks.

These are deliberately source-level checks: public provider callbacks cannot
inherit the panel route guard, but they must derive a tenant exclusively from
persisted provider credentials before invoking the tenant-scoped service.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROUTE = ROOT / "backend" / "routes" / "agente_whatsapp.py"


def _source() -> str:
    return ROUTE.read_text(encoding="utf-8")


def _webhook_section(source: str) -> str:
    start = source.index("webhook_router = APIRouter")
    end = source.index("@router.get(\"/dashboard\"")
    return source[start:end]


def test_agente_whatsapp_public_webhooks_use_a_separate_unguarded_router():
    source = _source()
    webhook = _webhook_section(source)

    assert 'router = APIRouter(' in source
    assert "block_unsafe_wave6_route" not in source
    assert 'webhook_router = APIRouter(prefix="/agente-whatsapp"' in source
    assert '@webhook_router.get("/webhook/meta"' in webhook
    assert '@webhook_router.post("/webhook/meta"' in webhook
    assert '@webhook_router.post("/webhook/evolution"' in webhook
    assert "block_unsafe_wave6_route" not in webhook
    assert "panel_wave6_context" not in webhook


def test_meta_webhook_resolves_exactly_one_persisted_tenant_and_verifies_signature():
    source = _source()
    webhook = _webhook_section(source)

    # The token and phone number are persisted, tenant-owned integration
    # attributes.  A supplied tenant id must never select an account.
    assert "whatsapp_phone_number_id" in source
    assert "whatsapp_webhook_verify_token_hash" in source
    assert "hashlib.sha256" in source
    assert "len(matches) != 1" in source
    assert "X-Hub-Signature-256" in webhook
    assert "hmac.compare_digest" in webhook
    assert "TenantSource.WEBHOOK" in webhook
    assert "trusted_process_context" in webhook
    assert "AgenteWhatsAppService(db, tenant_context).process_meta_webhook(payload)" in webhook
    assert "request.query_params.get(\"tenant_id\")" not in webhook


def test_evolution_webhook_fails_closed_without_a_persisted_instance_mapping():
    source = _source()
    webhook = _webhook_section(source)

    assert "_evolution_connection_for_instance" in webhook
    assert "Evolution nao configurado para este webhook." in webhook
    assert "status_code=403" in webhook
    assert "AgenteWhatsAppService(db, tenant_context).process_evolution_webhook(payload)" in webhook
