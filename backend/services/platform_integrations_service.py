"""Secret-free cross-tenant integration inventory."""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import text

from backend.services.platform_operations_common import parse_datetime, safe_identifier, safe_label, utcnow


CATEGORY_LABELS = {
    "marketing": "Marketing e mensageria",
    "advertising": "Midia paga",
    "payments": "Pagamentos",
}
HEALTHY = {"active", "connected", "configured", "healthy", "ok", "success", "validated"}
DEGRADED = {"attention", "degraded", "pending", "partial", "testing"}
FAILED = {"error", "failed", "invalid", "unhealthy"}


def _status(value, *, configured: bool) -> str:
    normalized = safe_identifier(value)
    if normalized in HEALTHY:
        return "healthy"
    if normalized in DEGRADED:
        return "degraded"
    if normalized in FAILED:
        return "failed"
    if normalized in {"disconnected", "disabled", "inactive", "not_configured", "not_tested"}:
        return "degraded" if configured else "unknown"
    return "unknown"


class IntegrationAdapter:
    category: str

    def load(self, db) -> list[dict]:
        raise NotImplementedError


class MarketingIntegrationAdapter(IntegrationAdapter):
    category = "marketing"

    def load(self, db) -> list[dict]:
        rows = db.execute(text("""
            SELECT ic.id, ic.tenant_id, t.name AS tenant_name,
                   ic.integration_type AS provider, ic.status,
                   (ic.credentials_json IS NOT NULL AND ic.credentials_json <> '{}') AS configured,
                   ic.last_sync_at, ic.updated_at, (ic.last_error IS NOT NULL) AS error_present
            FROM integration_connections ic
            JOIN tenants t ON t.id = ic.tenant_id AND t.deleted_at IS NULL
            WHERE ic.tenant_id IS NOT NULL
        """)).mappings().all()
        return [dict(row) for row in rows]


class AdvertisingIntegrationAdapter(IntegrationAdapter):
    category = "advertising"

    def load(self, db) -> list[dict]:
        rows = db.execute(text("""
            SELECT ai.id, ai.tenant_id, t.name AS tenant_name,
                   ai.platform AS provider, ai.status,
                   (ai.access_token_encrypted IS NOT NULL OR ai.refresh_token_encrypted IS NOT NULL) AS configured,
                   ai.last_sync_at, ai.updated_at, (ai.last_error IS NOT NULL) AS error_present
            FROM ad_platform_integrations ai
            JOIN tenants t ON t.id = ai.tenant_id AND t.deleted_at IS NULL
            WHERE ai.tenant_id IS NOT NULL
        """)).mappings().all()
        return [dict(row) for row in rows]


class PaymentIntegrationAdapter(IntegrationAdapter):
    category = "payments"

    def load(self, db) -> list[dict]:
        rows = db.execute(text("""
            SELECT pc.id, pc.tenant_id, t.name AS tenant_name,
                   pc.mp_enabled, pc.mp_access_token IS NOT NULL AS mp_configured,
                   pc.mp_last_health_check_status AS mp_status,
                   pc.mp_last_health_check_at AS mp_checked_at,
                   pc.mp_last_health_check_message IS NOT NULL AS mp_error,
                   pc.asaas_enabled, pc.asaas_api_key IS NOT NULL AS asaas_configured,
                   pc.asaas_last_health_check_status AS asaas_status,
                   pc.asaas_last_health_check_at AS asaas_checked_at,
                   pc.asaas_last_health_check_message IS NOT NULL AS asaas_error,
                   pc.updated_at
            FROM payment_gateway_config pc
            JOIN tenants t ON t.id = pc.tenant_id AND t.deleted_at IS NULL
            WHERE pc.tenant_id IS NOT NULL
        """)).mappings().all()
        result: list[dict] = []
        for source in rows:
            row = dict(source)
            for provider in ("mercado_pago", "asaas"):
                prefix = "mp" if provider == "mercado_pago" else "asaas"
                enabled = bool(row.get(f"{prefix}_enabled"))
                configured = enabled and bool(row.get(f"{prefix}_configured"))
                result.append({
                    "id": f"{row['id']}:{provider}",
                    "tenant_id": row["tenant_id"],
                    "tenant_name": row["tenant_name"],
                    "provider": provider,
                    "status": row.get(f"{prefix}_status") if enabled else "disabled",
                    "configured": configured,
                    "last_sync_at": row.get(f"{prefix}_checked_at"),
                    "updated_at": row.get("updated_at"),
                    "error_present": bool(row.get(f"{prefix}_error")),
                })
        return result


class PlatformIntegrationsService:
    def __init__(self, db, *, adapters: list[IntegrationAdapter] | None = None):
        self.db = db
        self.adapters = adapters or [
            MarketingIntegrationAdapter(),
            AdvertisingIntegrationAdapter(),
            PaymentIntegrationAdapter(),
        ]

    def _connections(self) -> list[dict]:
        result: list[dict] = []
        for adapter in self.adapters:
            for row in adapter.load(self.db):
                configured = bool(row.get("configured"))
                result.append({
                    "id": safe_label(row.get("id"), max_length=180),
                    "tenant": {
                        "id": safe_label(row.get("tenant_id"), max_length=100),
                        "name": safe_label(row.get("tenant_name"), max_length=200),
                    },
                    "category": adapter.category,
                    "provider": safe_identifier(row.get("provider")),
                    "status": _status(row.get("status"), configured=configured),
                    "configured": configured,
                    "last_sync_at": parse_datetime(row.get("last_sync_at")),
                    "updated_at": parse_datetime(row.get("updated_at")),
                    "error_present": bool(row.get("error_present")),
                })
        result.sort(key=lambda item: (item["updated_at"] or item["last_sync_at"] or utcnow().replace(year=1970)), reverse=True)
        return result

    def overview(self) -> dict:
        rows = self._connections()
        categories: dict[str, dict] = defaultdict(lambda: {
            "total": 0, "healthy": 0, "degraded": 0, "failed": 0, "unknown": 0,
        })
        totals = {"healthy": 0, "degraded": 0, "failed": 0, "unknown": 0}
        for row in rows:
            categories[row["category"]]["total"] += 1
            categories[row["category"]][row["status"]] += 1
            totals[row["status"]] += 1
        return {
            "total": len(rows),
            "configured": sum(1 for row in rows if row["configured"]),
            **totals,
            "by_category": [{
                "key": key,
                "label": CATEGORY_LABELS[key],
                **categories[key],
            } for key in CATEGORY_LABELS],
            "generated_at": utcnow(),
        }

    def list_connections(
        self, *, page: int, page_size: int, tenant_id: str | None = None,
        provider: str | None = None, category: str | None = None,
        status: str | None = None,
    ) -> dict:
        rows = self._connections()
        if tenant_id:
            rows = [row for row in rows if row["tenant"]["id"] == tenant_id]
        if provider:
            normalized = safe_identifier(provider)
            rows = [row for row in rows if row["provider"] == normalized]
        if category:
            rows = [row for row in rows if row["category"] == category]
        if status:
            rows = [row for row in rows if row["status"] == status]
        total = len(rows)
        start = (page - 1) * page_size
        return {"items": rows[start:start + page_size], "page": page, "page_size": page_size, "total": total}
