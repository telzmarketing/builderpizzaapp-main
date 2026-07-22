"""Trusted tenant resolution for order-payment webhooks."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.models.payment_config import PaymentGatewayConfig
from backend.models.tenant import Tenant

_KEY_RE = re.compile(r"^[A-Za-z0-9_-]{24,160}$")
_PROVIDERS = frozenset({"mercado_pago", "asaas"})

class PaymentWebhookTenantResolutionError(DomainError):
    http_status = 404
    def __init__(self, message: str = "Endpoint de webhook nao reconhecido."):
        super().__init__(message, code="PaymentWebhookTenantResolutionError")

@dataclass(frozen=True)
class PaymentWebhookEndpoint:
    endpoint_key: str
    tenant_id: str
    provider: str

def parse_endpoint_catalog(raw_catalog: str) -> dict[str, PaymentWebhookEndpoint]:
    """Parse server-owned bindings; payload, headers and Host are not inputs."""
    try:
        payload = json.loads(raw_catalog or "{}")
    except (TypeError, json.JSONDecodeError) as exc:
        raise PaymentWebhookTenantResolutionError("Catalogo de webhooks invalido.") from exc
    if not isinstance(payload, dict):
        raise PaymentWebhookTenantResolutionError("Catalogo de webhooks invalido.")
    result: dict[str, PaymentWebhookEndpoint] = {}
    bindings: set[tuple[str, str]] = set()
    for endpoint_key, item in payload.items():
        if not isinstance(endpoint_key, str) or not _KEY_RE.fullmatch(endpoint_key):
            raise PaymentWebhookTenantResolutionError("Catalogo contem chave opaca invalida.")
        if not isinstance(item, dict):
            raise PaymentWebhookTenantResolutionError("Catalogo contem vinculo invalido.")
        tenant_id = str(item.get("tenant_id") or "").strip()
        provider = str(item.get("provider") or "").strip().lower()
        if not tenant_id or provider not in _PROVIDERS:
            raise PaymentWebhookTenantResolutionError("Catalogo contem vinculo incompleto.")
        binding = (tenant_id, provider)
        if binding in bindings:
            raise PaymentWebhookTenantResolutionError("Tenant e provider possuem mais de uma chave ativa.")
        bindings.add(binding)
        result[endpoint_key] = PaymentWebhookEndpoint(endpoint_key, tenant_id, provider)
    return result

class PaymentWebhookTenantResolver:
    def __init__(self, db: Session, raw_catalog: str):
        self._db = db
        self._catalog = parse_endpoint_catalog(raw_catalog)

    def resolve(self, endpoint_key: str, provider: str) -> PaymentWebhookEndpoint:
        binding = self._catalog.get(endpoint_key)
        if binding is None or binding.provider != (provider or "").strip().lower():
            raise PaymentWebhookTenantResolutionError()
        tenant = self._db.query(Tenant).filter(
            Tenant.id == binding.tenant_id, Tenant.status == "active", Tenant.deleted_at.is_(None)
        ).one_or_none()
        if tenant is None:
            raise PaymentWebhookTenantResolutionError("Tenant do webhook nao esta ativo.")
        configs = self._db.query(PaymentGatewayConfig).filter(
            PaymentGatewayConfig.tenant_id == binding.tenant_id
        ).limit(2).all()
        if len(configs) != 1:
            raise PaymentWebhookTenantResolutionError("Configuracao do gateway nao e inequivoca para o tenant.")
        return binding
