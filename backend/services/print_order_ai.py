"""Configured multimodal extraction for Print Pedido.

The provider only proposes structured data. It never writes an Order and never
maps an uncertain label to a catalog product. The caller remains responsible
for reconciliation, human review and idempotent confirmation.
"""
from __future__ import annotations

import json
import re
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from backend.models.agente_whatsapp import AgenteWhatsAppAISettings, agente_whatsapp_ai_settings_id
from backend.services.ai.factory import get_ai_provider


class VisionItem(BaseModel):
    external_name: str = Field(min_length=1, max_length=300)
    quantity: int = Field(default=1, ge=1, le=999)
    unit_price: Decimal | None = Field(default=None, ge=0, max_digits=20, decimal_places=2)
    total_price: Decimal | None = Field(default=None, ge=0, max_digits=20, decimal_places=2)
    selected_size: str | None = Field(default=None, max_length=80)
    flavor_names: list[str] = Field(default_factory=list, max_length=8)
    confidence: Decimal | None = Field(default=None, ge=0, le=1, max_digits=4, decimal_places=3)


class VisionFinancials(BaseModel):
    subtotal: Decimal | None = Field(default=None, ge=0, max_digits=20, decimal_places=2)
    delivery_fee: Decimal | None = Field(default=None, ge=0, max_digits=20, decimal_places=2)
    service_fee: Decimal | None = Field(default=None, ge=0, max_digits=20, decimal_places=2)
    store_discount: Decimal | None = Field(default=None, ge=0, max_digits=20, decimal_places=2)
    platform_discount: Decimal | None = Field(default=None, ge=0, max_digits=20, decimal_places=2)
    total_paid: Decimal | None = Field(default=None, ge=0, max_digits=20, decimal_places=2)


class VisionOrder(BaseModel):
    platform: str | None = None
    external_order_number: str | None = Field(default=None, max_length=120)
    customer_name: str | None = Field(default=None, max_length=200)
    customer_phone: str | None = Field(default=None, max_length=30)
    delivery_street: str | None = Field(default=None, max_length=300)
    delivery_city: str | None = Field(default=None, max_length=100)
    delivery_complement: str | None = Field(default=None, max_length=100)
    fulfillment_type: str | None = None
    payment_method: str | None = Field(default=None, max_length=40)
    items: list[VisionItem] = Field(default_factory=list, max_length=200)
    financials: VisionFinancials = Field(default_factory=VisionFinancials)
    uncertain_fields: list[str] = Field(default_factory=list, max_length=100)


VISION_PROMPT = """
Voce e o extrator multimodal do ERP Gran Torino. Analise a foto de uma comanda
de delivery e retorne SOMENTE um objeto JSON, sem markdown, com este contrato:
{
  "platform": "ifood|99food|keeta|unknown",
  "external_order_number": "numero impresso, sem inventar",
  "customer_name": "nome mesmo quando nao houver cabecalho Cliente",
  "customer_phone": null,
  "delivery_street": null,
  "delivery_city": null,
  "delivery_complement": null,
  "fulfillment_type": "delivery|pickup|unknown",
  "payment_method": "texto literal impresso, como Pago, ou null",
  "items": [{"external_name": "nome completo do item", "quantity": 1, "unit_price": null, "total_price": null, "selected_size": null, "flavor_names": [], "confidence": null}],
  "financials": {"subtotal": null, "delivery_fee": null, "service_fee": null, "store_discount": null, "platform_discount": null, "total_paid": null},
  "uncertain_fields": []
}
Regras: null quando nao estiver legivel; valores monetarios positivos mesmo quando
impressos com sinal negativo em promocoes; nao transforme cabecalhos, observacoes
ou nomes de colunas em itens; preserve o texto do item e todos os sabores.
""".strip()


def _clean_json(content: str) -> str:
    value = content.strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*|\s*```$", "", value, flags=re.I | re.S).strip()
    return value


def _money(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value)).quantize(Decimal("0.01"))
    text = str(value).strip().replace("R$", "").replace(" ", "")
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        return Decimal(text).quantize(Decimal("0.01"))
    except Exception:
        return None


def _normalize_response(raw: dict[str, Any]) -> dict[str, Any]:
    financials = raw.get("financials") if isinstance(raw.get("financials"), dict) else raw
    items = raw.get("items") if isinstance(raw.get("items"), list) else []
    normalized_items = []
    for item in items:
        if not isinstance(item, dict) or not str(item.get("external_name") or item.get("name") or "").strip():
            continue
        normalized_items.append({
            "external_name": str(item.get("external_name") or item.get("name")).strip()[:300],
            "quantity": item.get("quantity") or 1,
            "unit_price": _money(item.get("unit_price")),
            "total_price": _money(item.get("total_price")),
            "selected_size": item.get("selected_size"),
            "flavor_names": item.get("flavor_names") or [],
            "confidence": item.get("confidence"),
        })
    return {
        "platform": raw.get("platform"),
        "external_order_number": raw.get("external_order_number") or raw.get("order_number"),
        "customer_name": raw.get("customer_name") or raw.get("customer"),
        "customer_phone": raw.get("customer_phone") or raw.get("phone"),
        "delivery_street": raw.get("delivery_street") or raw.get("street"),
        "delivery_city": raw.get("delivery_city") or raw.get("city"),
        "delivery_complement": raw.get("delivery_complement") or raw.get("complement"),
        "fulfillment_type": raw.get("fulfillment_type"),
        "payment_method": raw.get("payment_method") or raw.get("payment"),
        "items": normalized_items,
        "financials": {key: _money(financials.get(key)) for key in (
            "subtotal", "delivery_fee", "service_fee", "store_discount", "platform_discount", "total_paid"
        )},
        "uncertain_fields": [str(value) for value in (raw.get("uncertain_fields") or [])],
    }


def extract_print_order_with_vision(db: Session, tenant_id: str, data: bytes, mime_type: str, manual_platform: str | None = None) -> tuple[dict[str, Any] | None, str | None]:
    """Use the Agente WhatsApp Atendimento provider, failing closed when unavailable.

    Gestor IA and the legacy ChatbotSettings are intentionally not consulted.
    """
    settings_id = agente_whatsapp_ai_settings_id(tenant_id)
    settings = db.query(AgenteWhatsAppAISettings).filter(
        AgenteWhatsAppAISettings.id == settings_id,
        AgenteWhatsAppAISettings.tenant_id == tenant_id,
    ).first()
    if settings is None:
        return None, "provedor_multimodal_nao_configurado"
    provider = get_ai_provider(settings)
    if not provider.is_configured() or not hasattr(provider, "generate_multimodal_json"):
        return None, "provedor_multimodal_nao_configurado"
    response = provider.generate_multimodal_json(VISION_PROMPT, data, mime_type, temperatura=0.0, max_tokens=3000)
    if response.error_reason or not response.content.strip():
        return None, response.error_reason or "resposta_multimodal_vazia"
    try:
        parsed = VisionOrder.model_validate(_normalize_response(json.loads(_clean_json(response.content))))
    except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as exc:
        return None, f"resposta_multimodal_invalida:{type(exc).__name__}"
    payload = parsed.model_dump(mode="json")
    payload["financials"] = {
        key: (float(value) if value is not None else None)
        for key, value in parsed.financials.model_dump().items()
    }
    for item, source in zip(payload.get("items", []), parsed.items):
        item["unit_price"] = float(source.unit_price) if source.unit_price is not None else None
        item["total_price"] = float(source.total_price) if source.total_price is not None else None
    if manual_platform and manual_platform != "unknown":
        payload["platform"] = manual_platform
    payload["parser"] = f"vision-{response.provider or 'configured'}-v1"
    payload["review_notes"] = ["Dados extraidos por IA multimodal; revise campos, itens, catalogo e valores antes de confirmar."]
    if parsed.uncertain_fields:
        payload["review_notes"].append("Campos com baixa certeza: " + ", ".join(parsed.uncertain_fields))
    return payload, None
