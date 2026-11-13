import json
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base
from backend.models.agente_whatsapp import AgenteWhatsAppAISettings
from backend.models.tenant import Tenant
from backend.services.print_order_ai import extract_print_order_with_vision
from backend.models.ai_credentials import TenantAICredential


class _ConfiguredVisionProvider:
    provider_name = "openai"

    def is_configured(self):
        return True

    def generate_multimodal_json(self, *args, **kwargs):
        return SimpleNamespace(
            provider="openai", error_reason="", model="gpt-4o-mini",
            content=json.dumps({
                "platform": "keeta", "external_order_number": "9399",
                "customer_name": "Edder Cezar Galvao de Souza", "fulfillment_type": "pickup",
                "payment_method": "Pago", "items": [{
                    "external_name": "Compre 1 Pizza e Ganhe 1 Guarana 2L", "quantity": 1,
                    "total_price": "71,99", "confidence": 0.98,
                }],
                "financials": {"subtotal": "71,99", "delivery_fee": "13,99", "service_fee": "0,99", "store_discount": "24,99", "platform_discount": "23,19", "total_paid": "38,79"},
                "uncertain_fields": ["payment_method"],
            }),
        )


def test_configured_vision_returns_structured_payload_without_writing_order(monkeypatch):
    monkeypatch.setattr("backend.services.print_order_ai.get_ai_provider", lambda settings: _ConfiguredVisionProvider())
    settings = SimpleNamespace(id="agente-whatsapp-ai:tenant-a", tenant_id="tenant-a")
    db = SimpleNamespace(query=lambda model: SimpleNamespace(filter=lambda *args: SimpleNamespace(first=lambda: settings)))

    parsed, reason = extract_print_order_with_vision(db, "tenant-a", b"image", "image/jpeg", "keeta")

    assert reason is None
    assert parsed["parser"] == "vision-openai-v1"
    assert parsed["external_order_number"] == "9399"
    assert parsed["financials"]["total_paid"] == 38.79
    assert parsed["uncertain_fields"] == ["payment_method"]


def test_vision_falls_back_when_provider_is_not_configured(monkeypatch):
    class _Unavailable:
        def is_configured(self): return False

    monkeypatch.setattr("backend.services.print_order_ai.get_ai_provider", lambda settings: _Unavailable())
    settings = SimpleNamespace(id="agente-whatsapp-ai:tenant-a", tenant_id="tenant-a")
    db = SimpleNamespace(query=lambda model: SimpleNamespace(filter=lambda *args: SimpleNamespace(first=lambda: settings)))

    parsed, reason = extract_print_order_with_vision(db, "tenant-a", b"image", "image/jpeg", "keeta")

    assert parsed is None
    assert reason == "provedor_multimodal_nao_configurado"


def test_print_order_resolves_the_configured_atendimento_provider(monkeypatch):
    from backend.models import (  # noqa: F401 - register the complete ORM relationship registry
        admin, agente_whatsapp, business_intelligence, campaign, chatbot, cmv, coupon,
        customer, customer_event, customer_identity, customer_contact_risk, delivery,
        exit_popup, finance, fiscal, gestao, gestor, home_config, idempotency,
        inventory, inventory_foundation, inventory_portion, inventory_receipts,
        inventory_traceability, kds_audit, kds_production, label, loyalty,
        marketing_intelligence, membership, order, order_board, partner_identification,
        paid_traffic, payment, payment_config, pcp, platform_audit, platform_operations,
        platform_rbac, platform_saas, preparation, print_order, product,
        product_promotion, production_vision, promotion, promotion_landing_page,
        rbac, salao, salao_page, shipping, shipping_v2, store_notification,
        store_operation, tenant, tenant_domain, tenant_domain_ssl, theme, upload_asset,
        upsell, whatsapp_gateway,
    )

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[Tenant.__table__, AgenteWhatsAppAISettings.__table__, TenantAICredential.__table__])
    db = sessionmaker(bind=engine)()
    db.add(AgenteWhatsAppAISettings(
        id="agente-whatsapp-ai:tenant-a",
        tenant_id="tenant-a",
        provider="openai",
        model="gpt-4o-mini",
        openai_api_key="atendimento-key",
    ))
    db.commit()
    captured = {}

    def fake_multimodal(self, *args, **kwargs):
        captured["provider"] = self.provider_name
        captured["model"] = self._model
        return SimpleNamespace(
            provider=self.provider_name,
            model=self._model,
            error_reason="",
            content=json.dumps({"platform": "keeta", "external_order_number": "9399"}),
        )

    monkeypatch.setattr(
        "backend.services.ai.openai_provider.OpenAIProvider.generate_multimodal_json",
        fake_multimodal,
    )

    try:
        parsed, reason = extract_print_order_with_vision(db, "tenant-a", b"image", "image/jpeg", "keeta")
    finally:
        db.close()
        engine.dispose()

    assert reason is None
    assert parsed["parser"] == "vision-openai-v1"
    assert captured == {"provider": "openai", "model": "gpt-4o-mini"}
