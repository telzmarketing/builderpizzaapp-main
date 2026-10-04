from pathlib import Path

import pytest
from fastapi import HTTPException

from backend.config import get_settings
from backend.core.wave6_route_guard import block_unsafe_wave6_route


ROOT = Path(__file__).parents[1]


def test_wave6_route_guard_blocks_when_flag_is_enabled(monkeypatch):
    monkeypatch.setenv("MULTI_TENANT_WAVE6_ORM_ENABLED", "true")
    get_settings.cache_clear()

    with pytest.raises(HTTPException) as exc:
        block_unsafe_wave6_route()

    assert exc.value.status_code == 503
    assert "evitar acesso cruzado entre empresas" in str(exc.value.detail)
    get_settings.cache_clear()


def test_wave6_route_guard_allows_legacy_single_tenant_mode(monkeypatch):
    monkeypatch.delenv("MULTI_TENANT_WAVE6_ORM_ENABLED", raising=False)
    get_settings.cache_clear()

    block_unsafe_wave6_route()
    get_settings.cache_clear()


def test_whatsapp_surfaces_no_longer_depend_on_the_wave6_guard():
    migrated_routes = {
        "backend/routes/whatsapp_marketing.py",
        "backend/routes/agente_whatsapp.py",
    }

    for relative_path in migrated_routes:
        source = (ROOT / relative_path).read_text(encoding="utf-8")
        assert "block_unsafe_wave6_route" not in source, relative_path


def test_whatsapp_surfaces_are_migrated_and_marketing_bridge_is_tenant_aware():
    agent_source = (ROOT / "backend/routes/agente_whatsapp.py").read_text(encoding="utf-8")
    marketing_source = (ROOT / "backend/routes/whatsapp_marketing.py").read_text(encoding="utf-8")
    core_source = (ROOT / "backend/services/agente_whatsapp_service.py").read_text(encoding="utf-8")

    assert "block_unsafe_wave6_route" not in agent_source
    assert "block_unsafe_wave6_route" not in marketing_source
    assert "AgenteWhatsAppWebhookDeferred" not in agent_source
    assert "tenant_context=tenant_context" in marketing_source
    assert "AgenteWhatsAppService(db, tenant_context)" in marketing_source
    assert "AgenteWhatsAppOutboxService(\n                self._db,\n                self._tenant_context" in core_source
    assert "AgenteWhatsAppProcessingService(\n                        self._db,\n                        self._tenant_context" in core_source


def test_migrated_wave6_surfaces_use_trusted_tenant_context():
    migrated_routes = {
        "backend/routes/customer_events.py": (
            "public_wave6_context",
            "panel_wave6_context",
            "wave6_tenant_id(context)",
            "CustomerEvent.tenant_id == tenant_id",
        ),
        "backend/routes/exit_popup.py": (
            "public_wave6_context",
            "panel_wave6_context",
            "wave6_tenant_id(context)",
            "ExitPopupConfig.tenant_id == tenant_id",
        ),
        "backend/routes/crm.py": (
                "panel_wave6_context",
                "tenant_id = _tenant(context)",
            "_q(db, CrmCard, tenant_id)",
            "_q(db, CustomerGroup, tenant_id)",
            "_q(db, CustomerTimeline,",
            "CrmCardNote(id=str(uuid.uuid4()), tenant_id=tenant_id",
            "CrmCardHistory(id=str(uuid.uuid4()), tenant_id=tenant_id",
            "tenant_id=tenant_id",
            "customer_group_members (id, tenant_id, group_id, customer_id",
        ),
        "backend/routes/marketing_workflow.py": (
            "panel_wave6_context",
            "tenant_id = wave6_tenant_id(context)",
            "WHERE tenant_id = :tenant_id",
            "tenant_id, workflow_id",
        ),
        "backend/routes/marketing.py": (
            "panel_wave6_context",
            "public_wave6_context",
            "MarketingCampaign.tenant_id == tenant_id",
            "VisitorProfile.tenant_id == tenant_id",
            "IntegrationConnection.tenant_id == tenant_id",
        ),
        "backend/routes/chatbot.py": (
            "public_wave6_context",
            "wave6_tenant_id(context)",
            "ChatbotMessage.tenant_id == tenant_id",
        ),
        "backend/routes/admin_chatbot.py": (
            "panel_wave6_context",
            "ChatbotFAQ.tenant_id == _tenant_id(db)",
            "ChatbotConversation.tenant_id == tenant_id",
        ),
        "backend/routes/email_marketing.py": (
            "panel_wave6_context",
            "wave6_tenant_id",
            "EmailConfig.tenant_id == tenant_id",
            "WHERE em.tenant_id = :tenant_id",
        ),
        "backend/routes/ads_oauth.py": (
            "panel_wave6_context",
            "WAVE6_SESSION_TENANT_KEY",
            "AdsOAuthState.tenant_id == tenant_id",
            "AdsCampaign.tenant_id == tenant_id",
            "AdsUtmLink.tenant_id == _tenant_id(db)",
            "AdsPixel.tenant_id == _tenant_id(db)",
            "WHERE tenant_id = :tenant_id",
        ),
        "backend/routes/marketing_intelligence.py": (
            "panel_wave6_context",
            "WAVE6_SESSION_TENANT_KEY",
            "wave6_tenant_id",
        ),
        "backend/routes/bi.py": (
            "panel_wave6_context",
            "WAVE6_SESSION_TENANT_KEY",
            "wave6_tenant_id",
        ),
    }

    for relative_path, expected_fragments in migrated_routes.items():
        source = (ROOT / relative_path).read_text(encoding="utf-8")
        assert "block_unsafe_wave6_route" not in source, relative_path
        for fragment in expected_fragments:
            assert fragment in source, f"{relative_path}: {fragment}"
