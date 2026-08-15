"""Cached storage metrics projection; requests never walk the filesystem."""
from __future__ import annotations

from sqlalchemy import and_

from backend.models.platform_saas import SaaSPlan, TenantSubscription
from backend.models.tenant import Tenant
from backend.services.platform_operations_common import (
    PlatformSnapshotReader,
    bounded_percent,
    non_negative_int,
    normalize_health,
    safe_label,
    snapshot_freshness,
)


def _byte_count(value) -> dict:
    source = value if isinstance(value, dict) else {}
    return {
        "bytes": non_negative_int(source.get("bytes")),
        "files": non_negative_int(source.get("files")),
    }


class PlatformStorageService:
    def __init__(self, db, *, snapshots: PlatformSnapshotReader | None = None):
        self.db = db
        self.snapshots = snapshots or PlatformSnapshotReader()

    def _snapshot(self) -> tuple[dict | None, object, bool]:
        payload = self.snapshots.read_json("storage.json")
        generated_at, stale = snapshot_freshness(payload, max_age_seconds=900)
        return payload, generated_at, stale

    def overview(self) -> dict:
        payload, generated_at, stale = self._snapshot()
        disk_source = payload.get("disk", {}) if isinstance(payload, dict) else {}
        total = non_negative_int(disk_source.get("total_bytes"))
        used = min(total, non_negative_int(disk_source.get("used_bytes"))) if total else non_negative_int(disk_source.get("used_bytes"))
        free = min(total, non_negative_int(disk_source.get("free_bytes"))) if total else non_negative_int(disk_source.get("free_bytes"))
        usage_percent = bounded_percent(
            disk_source.get("usage_percent")
            if disk_source.get("usage_percent") is not None
            else (used * 100 / total if total else 0)
        )
        status = "unknown" if payload is None else normalize_health(payload.get("status"))
        if stale and status == "healthy":
            status = "degraded"
        return {
            "generated_at": generated_at,
            "stale": stale,
            "status": status,
            "disk": {
                "total_bytes": total,
                "used_bytes": used,
                "free_bytes": free,
                "usage_percent": usage_percent,
            },
            "uploads": _byte_count((payload or {}).get("uploads")),
            "optimized": _byte_count((payload or {}).get("optimized")),
            "baileys": _byte_count((payload or {}).get("baileys")),
            "legacy_unattributed": _byte_count((payload or {}).get("legacy_unattributed")),
        }

    def list_tenants(
        self, *, page: int, page_size: int, q: str | None = None,
        usage_state: str | None = None,
    ) -> dict:
        payload, _generated_at, _stale = self._snapshot()
        raw_rows = payload.get("tenants", []) if isinstance(payload, dict) else []
        if not isinstance(raw_rows, list):
            raw_rows = []
        usage_by_tenant: dict[str, dict] = {}
        for source in raw_rows:
            if not isinstance(source, dict):
                continue
            tenant_id = safe_label(source.get("tenant_id"), default="", max_length=100)
            if not tenant_id:
                continue
            current = usage_by_tenant.setdefault(tenant_id, {"bytes": 0, "files": 0})
            current["bytes"] += non_negative_int(source.get("bytes"))
            current["files"] += non_negative_int(source.get("files"))
        if not usage_by_tenant:
            return {"items": [], "page": page, "page_size": page_size, "total": 0}

        rows = (
            self.db.query(Tenant.id, Tenant.name, SaaSPlan.max_storage_mb)
            .outerjoin(
                TenantSubscription,
                and_(
                    TenantSubscription.tenant_id == Tenant.id,
                    TenantSubscription.ended_at.is_(None),
                ),
            )
            .outerjoin(SaaSPlan, SaaSPlan.id == TenantSubscription.plan_id)
            .filter(Tenant.id.in_(list(usage_by_tenant)), Tenant.deleted_at.is_(None))
            .all()
        )
        items = []
        for row in rows:
            usage = usage_by_tenant[row.id]
            limit_bytes = (
                max(0, int(row.max_storage_mb)) * 1024 * 1024
                if row.max_storage_mb is not None else None
            )
            percent = (
                round(usage["bytes"] * 100 / limit_bytes, 2)
                if limit_bytes and limit_bytes > 0 else None
            )
            if percent is None:
                state = "unknown"
            elif percent >= 90:
                state = "critical"
            elif percent >= 75:
                state = "warning"
            else:
                state = "normal"
            items.append({
                "tenant": {"id": row.id, "name": safe_label(row.name)},
                "bytes": usage["bytes"],
                "files": usage["files"],
                "limit_bytes": limit_bytes,
                "usage_percent": percent,
                "usage_state": state,
            })
        if q:
            normalized_q = q.strip().casefold()
            items = [item for item in items if normalized_q in item["tenant"]["name"].casefold() or normalized_q in item["tenant"]["id"].casefold()]
        if usage_state:
            items = [item for item in items if item["usage_state"] == usage_state]
        items.sort(key=lambda item: (item["bytes"], item["tenant"]["name"]), reverse=True)
        total = len(items)
        start = (page - 1) * page_size
        return {"items": items[start:start + page_size], "page": page, "page_size": page_size, "total": total}
