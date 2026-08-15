"""Redacted operational error capture and audited lifecycle management."""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections.abc import Mapping

from sqlalchemy import func

from backend.models.platform_operations import PlatformErrorEvent
from backend.models.tenant import Tenant
from backend.services.platform_audit_service import PlatformAuditService
from backend.services.platform_operations_common import (
    PlatformOperationConflict,
    PlatformOperationNotFound,
    parse_datetime,
    redact_text,
    safe_identifier,
    safe_label,
    utcnow,
)


SEVERITIES = {"info", "warning", "error", "critical"}
CONTEXT_KEYS = {"component", "operation", "phase", "provider", "queue"}
UUID_SEGMENT_RE = re.compile(r"^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$", re.I)


def _safe_path(value) -> str | None:
    raw = str(value or "").split("?", 1)[0].strip()
    if not raw.startswith("/"):
        return None
    segments = []
    for segment in raw.split("/"):
        if UUID_SEGMENT_RE.match(segment) or segment.isdigit() or len(segment) > 80:
            segments.append(":id")
        else:
            segments.append(re.sub(r"[^A-Za-z0-9_.:-]", "", segment)[:80])
    normalized = "/".join(segments)[:300]
    return normalized or None


def _safe_context(context: Mapping | None) -> str:
    if not isinstance(context, Mapping):
        return "{}"
    payload = {}
    for raw_key, value in context.items():
        key = str(raw_key)
        if key in CONTEXT_KEYS:
            payload[key] = redact_text(value, max_length=160)
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


class PlatformErrorService:
    def __init__(self, db):
        self.db = db
        self.audit = PlatformAuditService(db)

    def capture_exception(
        self, exception: BaseException, *, source: str = "api",
        tenant_id: str | None = None, severity: str = "error",
        error_code: str | None = None, method: str | None = None,
        path: str | None = None, request_id: str | None = None,
        correlation_id: str | None = None, context: Mapping | None = None,
    ) -> str | None:
        """Persist a sanitized fingerprint without ever propagating capture failure."""
        try:
            normalized_source = safe_identifier(source)
            normalized_severity = safe_identifier(severity)
            if normalized_severity not in SEVERITIES:
                normalized_severity = "error"
            if tenant_id:
                tenant_exists = self.db.query(Tenant.id).filter(
                    Tenant.id == tenant_id,
                    Tenant.deleted_at.is_(None),
                ).first()
                if tenant_exists is None:
                    tenant_id = None
            message = redact_text(str(exception), max_length=1000)
            exception_type = safe_identifier(
                type(exception).__name__, max_length=160
            )
            code = safe_identifier(error_code, default="", max_length=100) or None
            route_path = _safe_path(path)
            fingerprint_basis = "|".join((
                normalized_source,
                code or "",
                exception_type,
                route_path or "",
                message,
            ))
            fingerprint = hashlib.sha256(fingerprint_basis.encode("utf-8")).hexdigest()
            query = self.db.query(PlatformErrorEvent).filter(
                PlatformErrorEvent.fingerprint == fingerprint,
                PlatformErrorEvent.source == normalized_source,
                PlatformErrorEvent.status == "open",
            )
            query = (
                query.filter(PlatformErrorEvent.tenant_id == tenant_id)
                if tenant_id is not None
                else query.filter(PlatformErrorEvent.tenant_id.is_(None))
            )
            row = query.with_for_update().first()
            now = utcnow()
            if row is None:
                row = PlatformErrorEvent(
                    id=str(uuid.uuid4()),
                    tenant_id=tenant_id,
                    fingerprint=fingerprint,
                    source=normalized_source,
                    severity=normalized_severity,
                    status="open",
                    error_code=code,
                    exception_type=exception_type,
                    message=message,
                    method=safe_identifier(method, default="", max_length=12).upper() or None,
                    path=route_path,
                    request_id=safe_identifier(request_id, default="", max_length=100) or None,
                    correlation_id=safe_identifier(correlation_id, default="", max_length=100) or None,
                    occurrence_count=1,
                    first_seen_at=now,
                    last_seen_at=now,
                    sample_context_json=_safe_context(context),
                    created_at=now,
                    updated_at=now,
                )
                self.db.add(row)
            else:
                row.occurrence_count += 1
                row.last_seen_at = now
                row.updated_at = now
                if normalized_severity == "critical":
                    row.severity = "critical"
            self.db.commit()
            return row.id
        except Exception:
            self.db.rollback()
            return None

    @staticmethod
    def _public(row: PlatformErrorEvent, tenant_name: str | None = None, *, detail: bool = False) -> dict:
        payload = {
            "id": row.id,
            "tenant": ({"id": row.tenant_id, "name": safe_label(tenant_name)} if row.tenant_id else None),
            "fingerprint": row.fingerprint,
            "source": safe_identifier(row.source),
            "severity": row.severity,
            "status": row.status,
            "error_code": safe_identifier(row.error_code, default="", max_length=100) or None,
            "exception_type": safe_identifier(row.exception_type, default="", max_length=160) or None,
            "message": redact_text(row.message, max_length=1000),
            "method": safe_identifier(row.method, default="", max_length=12).upper() or None,
            "path": _safe_path(row.path),
            "request_id": safe_identifier(row.request_id, default="", max_length=100) or None,
            "occurrence_count": max(1, int(row.occurrence_count or 1)),
            "first_seen_at": row.first_seen_at,
            "last_seen_at": row.last_seen_at,
            "acknowledged_at": row.acknowledged_at,
            "resolved_at": row.resolved_at,
        }
        if detail:
            payload.update({
                "acknowledgement_note": redact_text(row.acknowledgement_note, max_length=1000) if row.acknowledgement_note else None,
                "resolution_note": redact_text(row.resolution_note, max_length=1000) if row.resolution_note else None,
            })
        return payload

    def overview(self) -> dict:
        summary = self.db.query(
            func.count(PlatformErrorEvent.id).filter(PlatformErrorEvent.status == "open").label("total_open"),
            func.count(PlatformErrorEvent.id).filter(
                PlatformErrorEvent.status == "open",
                PlatformErrorEvent.severity == "critical",
            ).label("critical_open"),
            func.count(PlatformErrorEvent.id).filter(PlatformErrorEvent.status == "acknowledged").label("acknowledged"),
            func.count(PlatformErrorEvent.id).filter(PlatformErrorEvent.status == "resolved").label("resolved"),
            func.max(PlatformErrorEvent.last_seen_at).label("last_seen_at"),
        ).one()
        source_rows = self.db.query(
            PlatformErrorEvent.source,
            func.count(PlatformErrorEvent.id).label("total_open"),
        ).filter(PlatformErrorEvent.status == "open").group_by(
            PlatformErrorEvent.source
        ).order_by(PlatformErrorEvent.source).all()
        return {
            "total_open": int(summary.total_open or 0),
            "critical_open": int(summary.critical_open or 0),
            "acknowledged": int(summary.acknowledged or 0),
            "resolved": int(summary.resolved or 0),
            "last_seen_at": summary.last_seen_at,
            "by_source": [{
                "source": safe_identifier(row.source),
                "total_open": int(row.total_open or 0),
            } for row in source_rows],
            "generated_at": utcnow(),
        }

    def list_events(
        self, *, page: int, page_size: int, tenant_id: str | None = None,
        source: str | None = None, severity: str | None = None,
        status: str | None = None, from_at=None, to_at=None,
    ) -> dict:
        query = self.db.query(PlatformErrorEvent, Tenant.name).outerjoin(
            Tenant, Tenant.id == PlatformErrorEvent.tenant_id
        )
        if tenant_id:
            query = query.filter(PlatformErrorEvent.tenant_id == tenant_id)
        if source:
            query = query.filter(PlatformErrorEvent.source == safe_identifier(source))
        if severity:
            query = query.filter(PlatformErrorEvent.severity == severity)
        if status:
            query = query.filter(PlatformErrorEvent.status == status)
        if from_at:
            query = query.filter(PlatformErrorEvent.last_seen_at >= from_at)
        if to_at:
            query = query.filter(PlatformErrorEvent.last_seen_at <= to_at)
        total = query.count()
        rows = query.order_by(
            PlatformErrorEvent.last_seen_at.desc(), PlatformErrorEvent.id
        ).offset((page - 1) * page_size).limit(page_size).all()
        return {
            "items": [self._public(row, tenant_name) for row, tenant_name in rows],
            "page": page,
            "page_size": page_size,
            "total": total,
        }

    def get_event(self, error_id: str) -> dict:
        result = self.db.query(PlatformErrorEvent, Tenant.name).outerjoin(
            Tenant, Tenant.id == PlatformErrorEvent.tenant_id
        ).filter(PlatformErrorEvent.id == error_id).first()
        if result is None:
            raise PlatformOperationNotFound("Erro operacional nao encontrado.")
        return self._public(result[0], result[1], detail=True)

    def acknowledge(self, *, error_id: str, actor, note: str, request=None) -> dict:
        row = self.db.query(PlatformErrorEvent).filter(
            PlatformErrorEvent.id == error_id
        ).with_for_update().first()
        if row is None:
            raise PlatformOperationNotFound("Erro operacional nao encontrado.")
        if row.status != "open":
            raise PlatformOperationConflict("Apenas erros abertos podem ser reconhecidos.")
        now = utcnow()
        before = {"status": row.status}
        row.status = "acknowledged"
        row.acknowledged_by = actor.id
        row.acknowledged_at = now
        row.acknowledgement_note = redact_text(note, max_length=1000)
        row.updated_at = now
        self.audit.record(
            action="platform_error_acknowledged", actor=actor,
            tenant_id=row.tenant_id, resource_type="platform_error_event",
            resource_id=row.id, before=before, after={"status": row.status},
            reason=row.acknowledgement_note, request=request,
        )
        self.db.commit()
        return self.get_event(row.id)

    def resolve(self, *, error_id: str, actor, note: str, request=None) -> dict:
        row = self.db.query(PlatformErrorEvent).filter(
            PlatformErrorEvent.id == error_id
        ).with_for_update().first()
        if row is None:
            raise PlatformOperationNotFound("Erro operacional nao encontrado.")
        if row.status == "resolved":
            raise PlatformOperationConflict("Erro operacional ja resolvido.")
        now = utcnow()
        before = {"status": row.status}
        row.status = "resolved"
        row.resolved_by = actor.id
        row.resolved_at = now
        row.resolution_note = redact_text(note, max_length=1000)
        row.updated_at = now
        self.audit.record(
            action="platform_error_resolved", actor=actor,
            tenant_id=row.tenant_id, resource_type="platform_error_event",
            resource_id=row.id, before=before, after={"status": row.status},
            reason=row.resolution_note, request=request,
        )
        self.db.commit()
        return self.get_event(row.id)
