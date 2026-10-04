from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_meta_webhook_has_a_public_router_and_tenant_bound_writes():
    source = (ROOT / "backend/routes/whatsapp_marketing.py").read_text(encoding="utf-8")

    assert 'webhook_router = APIRouter(prefix="/whatsapp"' in source
    assert '@webhook_router.get("/webhook"' in source
    assert '@webhook_router.post("/webhook"' in source
    assert "X-Hub-Signature-256" in source
    assert "hmac.compare_digest" in source
    assert "AND tenant_id = :tenant_id" in source
    assert 'WhatsAppCampaignDelivery.tenant_id == tenant_id' in source
    assert "def _meta_connection_for_verify_token" in source


def test_meta_webhook_identity_is_migrated_and_operational_target_advances():
    migration = (
        ROOT / "backend/migrations/versions/20261003_whatsapp_meta_webhook_tenant_keys.py"
    ).read_text(encoding="utf-8")
    main = (ROOT / "backend/main.py").read_text(encoding="utf-8")

    assert 'revision = "20261003_whatsapp_meta_webhook_tenant_keys"' in migration
    assert "whatsapp_phone_number_id" in migration
    assert "whatsapp_webhook_verify_token_hash" in migration
    assert "phone_number_id Meta duplicado" in migration
    assert main.count("whatsapp_marketing_routes.webhook_router") == 2
