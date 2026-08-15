"""Read-only, secret-free fleet view for the WhatsApp Gateway."""
from __future__ import annotations

import re

from sqlalchemy import text

from backend.services.platform_operations_common import (
    PlatformOperationNotFound,
    PlatformSnapshotReader,
    normalize_health,
    parse_datetime,
    redact_text,
    safe_identifier,
    safe_label,
    snapshot_freshness,
)


CONNECTED = {"connected", "open", "online", "ready"}
DISCONNECTED = {"closed", "created", "disconnected", "logged_out", "offline"}
DEGRADED = {"connecting", "reconnecting", "error", "failed", "degraded"}


def _instance_bucket(status) -> str:
    normalized = safe_identifier(status)
    if normalized in CONNECTED:
        return "connected"
    if normalized in DISCONNECTED:
        return "disconnected"
    if normalized in DEGRADED:
        return "degraded"
    return "unknown"


def _masked_phone(value) -> str | None:
    digits = re.sub(r"\D", "", str(value or ""))
    return f"***-{digits[-4:]}" if len(digits) >= 4 else None


class PlatformGatewayService:
    def __init__(self, db, *, snapshots: PlatformSnapshotReader | None = None):
        self.db = db
        self.snapshots = snapshots or PlatformSnapshotReader()

    def _runtime(self) -> dict:
        snapshot = self.snapshots.read_json("gateway.json")
        checked_at, stale = snapshot_freshness(snapshot, max_age_seconds=120)
        return {
            "status": "unknown" if snapshot is None else normalize_health(snapshot.get("status")),
            "version": (
                safe_identifier(snapshot.get("version"), default="", max_length=80) or None
                if snapshot is not None else None
            ),
            "checked_at": checked_at if snapshot is not None else None,
            "stale": stale,
        }

    def overview(self) -> dict:
        rows = self.db.execute(text("""
            SELECT i.status, i.last_seen_at, i.updated_at
              FROM whatsapp_gateway_instances i
              JOIN tenants t ON t.id = i.tenant_id AND t.deleted_at IS NULL
             WHERE i.tenant_id IS NOT NULL
        """)).mappings().all()
        counts = {"connected": 0, "disconnected": 0, "degraded": 0, "unknown": 0}
        last_activity = None
        for source in rows:
            row = dict(source)
            counts[_instance_bucket(row.get("status"))] += 1
            activity = parse_datetime(row.get("last_seen_at")) or parse_datetime(row.get("updated_at"))
            if activity is not None and (last_activity is None or activity > last_activity):
                last_activity = activity
        return {
            "runtime": self._runtime(),
            "total_instances": len(rows),
            **counts,
            "last_activity_at": last_activity,
        }

    def list_instances(
        self, *, page: int, page_size: int, tenant_id: str | None = None,
        status: str | None = None, provider: str | None = None,
    ) -> dict:
        params = {
            "tenant_id": tenant_id,
            "status": status,
            "provider": safe_identifier(provider) if provider else None,
            "offset": (page - 1) * page_size,
            "limit": page_size,
        }
        filters = """
            WHERE i.tenant_id IS NOT NULL
              AND (:tenant_id IS NULL OR i.tenant_id = :tenant_id)
              AND (:status IS NULL OR i.status = :status)
              AND (:provider IS NULL OR lower(i.provider) = :provider)
        """
        total = self.db.execute(text("""
            SELECT count(*) FROM whatsapp_gateway_instances i
            JOIN tenants t ON t.id=i.tenant_id AND t.deleted_at IS NULL
        """ + filters), params).scalar_one()
        rows = self.db.execute(text("""
            SELECT i.id, i.tenant_id, t.name AS tenant_name, i.name,
                   i.provider, i.status,
                   right(
                       regexp_replace(
                           coalesce(CAST(i.phone_number AS text), ''),
                           '\\D',
                           '',
                           'g'
                       ),
                       4
                   ) AS phone_suffix,
                   i.last_seen_at,
                   i.connected_at, i.disconnected_at, i.updated_at
              FROM whatsapp_gateway_instances i
              JOIN tenants t ON t.id=i.tenant_id AND t.deleted_at IS NULL
        """ + filters + """
             ORDER BY COALESCE(i.last_seen_at, i.updated_at) DESC, i.id
             OFFSET :offset LIMIT :limit
        """), params).mappings().all()
        items = []
        for source in rows:
            row = dict(source)
            items.append({
                "id": safe_label(row.get("id"), max_length=180),
                "tenant": {
                    "id": safe_label(row.get("tenant_id"), max_length=100),
                    "name": safe_label(row.get("tenant_name"), max_length=200),
                },
                "name": safe_label(row.get("name"), max_length=180),
                "provider": safe_identifier(row.get("provider")),
                "status": safe_identifier(row.get("status")),
                "phone_masked": _masked_phone(row.get("phone_suffix")),
                "last_seen_at": parse_datetime(row.get("last_seen_at")),
                "connected_at": parse_datetime(row.get("connected_at")),
                "disconnected_at": parse_datetime(row.get("disconnected_at")),
                "updated_at": parse_datetime(row.get("updated_at")),
            })
        return {"items": items, "page": page, "page_size": page_size, "total": int(total or 0)}

    def instance_logs(self, *, instance_id: str, tenant_id: str, limit: int) -> dict:
        exists = self.db.execute(text("""
            SELECT 1
              FROM whatsapp_gateway_instances i
              JOIN tenants t ON t.id=i.tenant_id AND t.deleted_at IS NULL
             WHERE i.id=:instance_id AND i.tenant_id=:tenant_id
        """), {"instance_id": instance_id, "tenant_id": tenant_id}).scalar_one_or_none()
        if exists is None:
            raise PlatformOperationNotFound("Instancia nao encontrada.")
        rows = self.db.execute(text("""
            SELECT id, action, status, message, created_at
              FROM whatsapp_gateway_logs
             WHERE instance_id=:instance_id AND tenant_id=:tenant_id
             ORDER BY created_at DESC LIMIT :limit
        """), {"instance_id": instance_id, "tenant_id": tenant_id, "limit": limit}).mappings().all()
        items = [{
            "id": safe_label(row.get("id"), max_length=180),
            "action": safe_identifier(row.get("action")),
            "status": safe_identifier(row.get("status")),
            "message": redact_text(row.get("message"), max_length=240),
            "created_at": parse_datetime(row.get("created_at")),
        } for row in rows]
        return {"items": items, "total": len(items)}
