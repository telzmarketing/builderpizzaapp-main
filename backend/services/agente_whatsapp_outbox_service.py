from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.models.agente_whatsapp import (
    AgenteWhatsAppInternalAlert,
    AgenteWhatsAppMessage,
    AgenteWhatsAppOutbox,
    AgenteWhatsAppProviderState,
    AgenteWhatsAppSession,
)
from backend.routes.whatsapp_marketing import (
    _get_config,
    _normalize_media_type,
    _normalize_provider,
    _send_evolution_api,
    _send_whatsapp_api,
)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _json_dump(value: dict[str, Any] | None) -> str:
    return json.dumps(value or {}, ensure_ascii=False)


def _json_load(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        data = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _seconds_between(later: datetime, earlier: datetime) -> float:
    if later.tzinfo and not earlier.tzinfo:
        earlier = earlier.replace(tzinfo=timezone.utc)
    if earlier.tzinfo and not later.tzinfo:
        later = later.replace(tzinfo=timezone.utc)
    return (later - earlier).total_seconds()


def _is_due(value: datetime | None, now: datetime) -> bool:
    if not value:
        return False
    return _seconds_between(now, value) >= 0


class AgenteWhatsAppOutboxService:
    def __init__(self, db: Session):
        self._db = db
        self._settings = get_settings()

    def enqueue_queued_messages(self, *, limit: int = 100) -> dict[str, int]:
        rows = (
            self._db.query(AgenteWhatsAppMessage, AgenteWhatsAppSession)
            .join(AgenteWhatsAppSession, AgenteWhatsAppSession.id == AgenteWhatsAppMessage.session_id)
            .outerjoin(AgenteWhatsAppOutbox, AgenteWhatsAppOutbox.message_id == AgenteWhatsAppMessage.id)
            .filter(
                AgenteWhatsAppMessage.direction == "outbound",
                AgenteWhatsAppMessage.provider_status == "queued",
                AgenteWhatsAppOutbox.id.is_(None),
            )
            .order_by(AgenteWhatsAppMessage.created_at.asc())
            .limit(limit)
            .all()
        )

        created = 0
        now = _now_utc()
        for message, session in rows:
            phone = (session.phone or "").strip()
            if not phone:
                message.provider_status = "failed"
                message.error = "Sessao sem telefone para envio."
                continue

            payload = _json_load(message.raw_payload_json)
            payload.update(
                {
                    "message_id": message.id,
                    "session_id": session.id,
                    "message_type": message.message_type,
                    "body": message.body,
                    "media_url": message.media_url,
                }
            )
            self._db.add(
                AgenteWhatsAppOutbox(
                    id=str(uuid.uuid4()),
                    message_id=message.id,
                    session_id=session.id,
                    customer_id=message.customer_id or session.customer_id,
                    phone=phone,
                    provider=_normalize_provider(session.provider),
                    status="pending",
                    attempts=0,
                    max_attempts=3,
                    idempotency_key=f"agente_whatsapp:{message.id}",
                    payload_json=_json_dump(payload),
                    next_attempt_at=now,
                    created_at=now,
                    updated_at=now,
                )
            )
            created += 1

        self._db.flush()
        return {"enqueued": created, "skipped": max(0, len(rows) - created)}

    def process_pending(self, *, limit: int = 20) -> dict[str, int]:
        enqueue_result = self.enqueue_queued_messages(limit=max(limit * 2, 20))
        now = _now_utc()
        rows = (
            self._db.query(AgenteWhatsAppOutbox)
            .filter(
                AgenteWhatsAppOutbox.status.in_(["pending", "failed"]),
                AgenteWhatsAppOutbox.attempts < AgenteWhatsAppOutbox.max_attempts,
                or_(AgenteWhatsAppOutbox.next_attempt_at.is_(None), AgenteWhatsAppOutbox.next_attempt_at <= now),
            )
            .order_by(AgenteWhatsAppOutbox.created_at.asc())
            .with_for_update(skip_locked=True)
            .limit(limit)
            .all()
        )

        sent = 0
        failed = 0
        for item in rows:
            ok = self._process_item(item)
            if ok:
                sent += 1
            else:
                failed += 1

        self._db.flush()
        return {
            "enqueued": enqueue_result["enqueued"],
            "processed": len(rows),
            "sent": sent,
            "failed": failed,
        }

    def list_outbox(self, *, status: str | None = None, limit: int = 100) -> list[AgenteWhatsAppOutbox]:
        q = self._db.query(AgenteWhatsAppOutbox)
        if status:
            q = q.filter(AgenteWhatsAppOutbox.status == status)
        return q.order_by(AgenteWhatsAppOutbox.created_at.desc()).limit(limit).all()

    def summary(self) -> dict[str, int]:
        rows = (
            self._db.query(AgenteWhatsAppOutbox.status, func.count(AgenteWhatsAppOutbox.id))
            .group_by(AgenteWhatsAppOutbox.status)
            .all()
        )
        counts = {"pending": 0, "processing": 0, "sent": 0, "failed": 0, "dead": 0}
        for status, total in rows:
            counts[status or "pending"] = int(total or 0)
        counts["queued_messages"] = (
            self._db.query(func.count(AgenteWhatsAppMessage.id))
            .outerjoin(AgenteWhatsAppOutbox, AgenteWhatsAppOutbox.message_id == AgenteWhatsAppMessage.id)
            .filter(
                AgenteWhatsAppMessage.direction == "outbound",
                AgenteWhatsAppMessage.provider_status == "queued",
                AgenteWhatsAppOutbox.id.is_(None),
            )
            .scalar()
            or 0
        )
        return counts

    def provider_states(self) -> list[AgenteWhatsAppProviderState]:
        providers = {
            row[0]
            for row in self._db.query(AgenteWhatsAppOutbox.provider).distinct().all()
            if row[0]
        }
        providers.update({"official", "evolution"})
        return [self._ensure_provider_state(provider) for provider in sorted(providers)]

    def alerts(self) -> dict[str, Any]:
        metrics = self.metrics()
        states = [self.serialize_provider_state(state) for state in self.provider_states()]
        internal = self.sync_internal_alerts(metrics=metrics, provider_states=states)
        alerts: list[dict[str, Any]] = []
        if metrics.get("dead", 0) > 0:
            alerts.append({
                "level": "critical",
                "code": "dead_items",
                "message": f"{metrics['dead']} item(ns) mortos exigem auditoria.",
            })
        if metrics.get("oldest_pending_age_seconds") and metrics["oldest_pending_age_seconds"] > 900:
            alerts.append({
                "level": "warning",
                "code": "old_pending",
                "message": "Existe item pendente ha mais de 15 minutos.",
            })
        for state in states:
            if state["status"] == "paused":
                alerts.append({
                    "level": "critical",
                    "code": "provider_paused",
                    "message": f"Provider {state['provider']} pausado: {state.get('paused_reason') or 'sem motivo informado'}.",
                })
        return {
            "alerts": alerts,
            "providers": states,
            "metrics": metrics,
            "internal_alerts": [self.serialize_internal_alert(alert) for alert in internal],
        }

    def metrics(self) -> dict[str, Any]:
        summary = self.summary()
        pending = (
            self._db.query(AgenteWhatsAppOutbox)
            .filter(AgenteWhatsAppOutbox.status.in_(["pending", "failed"]))
            .order_by(AgenteWhatsAppOutbox.created_at.asc())
            .first()
        )
        last_sent = (
            self._db.query(AgenteWhatsAppOutbox)
            .filter(AgenteWhatsAppOutbox.status == "sent")
            .order_by(AgenteWhatsAppOutbox.sent_at.desc().nullslast(), AgenteWhatsAppOutbox.updated_at.desc())
            .first()
        )
        last_error = (
            self._db.query(AgenteWhatsAppOutbox)
            .filter(AgenteWhatsAppOutbox.status.in_(["failed", "dead"]))
            .order_by(AgenteWhatsAppOutbox.updated_at.desc())
            .first()
        )
        sent_rows = (
            self._db.query(AgenteWhatsAppOutbox)
            .filter(AgenteWhatsAppOutbox.status == "sent", AgenteWhatsAppOutbox.sent_at.isnot(None))
            .order_by(AgenteWhatsAppOutbox.sent_at.desc())
            .limit(100)
            .all()
        )
        latencies = [
            max(0.0, _seconds_between(row.sent_at, row.created_at))
            for row in sent_rows
            if row.sent_at and row.created_at
        ]
        now = _now_utc()
        oldest_pending_age = None
        if pending and pending.created_at:
            oldest_pending_age = max(0, int(_seconds_between(now, pending.created_at)))
        return {
            **summary,
            "oldest_pending_age_seconds": oldest_pending_age,
            "avg_send_latency_seconds": round(sum(latencies) / len(latencies), 2) if latencies else None,
            "last_sent_at": last_sent.sent_at if last_sent else None,
            "last_error_at": last_error.updated_at if last_error else None,
            "last_error": last_error.error if last_error else None,
        }

    def retry(self, outbox_id: str) -> AgenteWhatsAppOutbox | None:
        item = self._db.query(AgenteWhatsAppOutbox).filter(AgenteWhatsAppOutbox.id == outbox_id).first()
        if not item:
            return None
        now = _now_utc()
        item.status = "pending"
        item.error = None
        item.next_attempt_at = now
        item.locked_at = None
        item.updated_at = now
        message = item.message
        if message:
            message.provider_status = "queued"
            message.error = None
        self._db.flush()
        return item

    def pause_provider(
        self,
        provider: str,
        *,
        reason: str = "Pausa manual pelo painel.",
        minutes: int | None = None,
    ) -> AgenteWhatsAppProviderState:
        state = self._ensure_provider_state(provider)
        now = _now_utc()
        pause_minutes = minutes if minutes is not None else self._settings.AGENTE_WHATSAPP_PROVIDER_PAUSE_MINUTES
        state.status = "paused"
        state.paused_at = now
        state.paused_until = now + timedelta(minutes=max(1, pause_minutes))
        state.paused_reason = reason
        state.updated_at = now
        self._db.flush()
        return state

    def resume_provider(self, provider: str) -> AgenteWhatsAppProviderState:
        state = self._ensure_provider_state(provider)
        now = _now_utc()
        state.status = "active"
        state.consecutive_failures = 0
        state.paused_at = None
        state.paused_until = None
        state.paused_reason = None
        state.updated_at = now
        self._db.flush()
        return state

    def list_internal_alerts(self, *, status: str | None = "active", limit: int = 50) -> list[AgenteWhatsAppInternalAlert]:
        self.sync_internal_alerts()
        q = self._db.query(AgenteWhatsAppInternalAlert)
        if status:
            q = q.filter(AgenteWhatsAppInternalAlert.status == status)
        return q.order_by(AgenteWhatsAppInternalAlert.last_seen_at.desc()).limit(limit).all()

    def acknowledge_internal_alert(self, alert_id: str) -> AgenteWhatsAppInternalAlert | None:
        alert = self._db.query(AgenteWhatsAppInternalAlert).filter(AgenteWhatsAppInternalAlert.id == alert_id).first()
        if not alert:
            return None
        now = _now_utc()
        alert.status = "acknowledged"
        alert.acknowledged_at = now
        alert.updated_at = now
        self._db.flush()
        return alert

    def sync_internal_alerts(
        self,
        *,
        metrics: dict[str, Any] | None = None,
        provider_states: list[dict[str, Any]] | None = None,
    ) -> list[AgenteWhatsAppInternalAlert]:
        metrics = metrics or self.metrics()
        provider_states = provider_states or [self.serialize_provider_state(state) for state in self.provider_states()]
        now = _now_utc()
        desired: dict[str, dict[str, Any]] = {}

        dead_since = now - timedelta(minutes=max(1, self._settings.AGENTE_WHATSAPP_DEAD_ALERT_AFTER_MINUTES))
        dead_count = (
            self._db.query(func.count(AgenteWhatsAppOutbox.id))
            .filter(AgenteWhatsAppOutbox.status == "dead", AgenteWhatsAppOutbox.updated_at <= dead_since)
            .scalar()
            or 0
        )
        if dead_count:
            desired["agente_whatsapp:dead_items"] = {
                "alert_type": "dead_items",
                "level": "critical",
                "title": "AGENTE WHATSAPP com itens mortos",
                "message": f"{dead_count} item(ns) da fila estao mortos ha mais de {self._settings.AGENTE_WHATSAPP_DEAD_ALERT_AFTER_MINUTES} minuto(s).",
                "payload": {"dead_count": dead_count, "metrics": metrics},
            }

        for state in provider_states:
            if state.get("status") == "paused":
                provider = state["provider"]
                desired[f"agente_whatsapp:provider_paused:{provider}"] = {
                    "alert_type": "provider_paused",
                    "level": "critical",
                    "title": f"Provider {provider} pausado",
                    "message": state.get("paused_reason") or f"Provider {provider} pausado pelo AGENTE WHATSAPP.",
                    "payload": {"provider": provider, "state": state},
                }

        if metrics.get("oldest_pending_age_seconds") and metrics["oldest_pending_age_seconds"] > 900:
            desired["agente_whatsapp:old_pending"] = {
                "alert_type": "old_pending",
                "level": "warning",
                "title": "Fila do AGENTE WHATSAPP atrasada",
                "message": "Existe item pendente ha mais de 15 minutos.",
                "payload": {"metrics": metrics},
            }

        active_keys = set(desired)
        current_alerts = (
            self._db.query(AgenteWhatsAppInternalAlert)
            .filter(AgenteWhatsAppInternalAlert.dedupe_key.like("agente_whatsapp:%"))
            .all()
        )
        by_key = {alert.dedupe_key: alert for alert in current_alerts}

        for key, data in desired.items():
            alert = by_key.get(key)
            if not alert:
                alert = AgenteWhatsAppInternalAlert(
                    id=str(uuid.uuid4()),
                    dedupe_key=key,
                    alert_type=data["alert_type"],
                    level=data["level"],
                    title=data["title"],
                    message=data["message"],
                    payload_json=_json_dump(data["payload"]),
                    status="active",
                    first_seen_at=now,
                    last_seen_at=now,
                    created_at=now,
                    updated_at=now,
                )
                self._db.add(alert)
                by_key[key] = alert
            else:
                alert.alert_type = data["alert_type"]
                alert.level = data["level"]
                alert.title = data["title"]
                alert.message = data["message"]
                alert.payload_json = _json_dump(data["payload"])
                if alert.status not in {"active", "acknowledged"}:
                    alert.status = "active"
                alert.resolved_at = None
                alert.last_seen_at = now
                alert.updated_at = now

        for alert in current_alerts:
            if alert.dedupe_key not in active_keys and alert.status != "resolved":
                alert.status = "resolved"
                alert.resolved_at = now
                alert.updated_at = now

        self._db.flush()
        return [by_key[key] for key in sorted(active_keys) if key in by_key]

    def serialize_provider_state(self, state: AgenteWhatsAppProviderState) -> dict[str, Any]:
        return {
            "id": state.id,
            "provider": state.provider,
            "status": state.status,
            "consecutive_failures": state.consecutive_failures,
            "failure_threshold": state.failure_threshold,
            "last_failure_at": state.last_failure_at,
            "last_success_at": state.last_success_at,
            "paused_at": state.paused_at,
            "paused_until": state.paused_until,
            "paused_reason": state.paused_reason,
            "created_at": state.created_at,
            "updated_at": state.updated_at,
        }

    def serialize_internal_alert(self, alert: AgenteWhatsAppInternalAlert) -> dict[str, Any]:
        return {
            "id": alert.id,
            "alert_type": alert.alert_type,
            "level": alert.level,
            "status": alert.status,
            "title": alert.title,
            "message": alert.message,
            "dedupe_key": alert.dedupe_key,
            "payload": _json_load(alert.payload_json),
            "first_seen_at": alert.first_seen_at,
            "last_seen_at": alert.last_seen_at,
            "acknowledged_at": alert.acknowledged_at,
            "resolved_at": alert.resolved_at,
            "created_at": alert.created_at,
            "updated_at": alert.updated_at,
        }

    def serialize_outbox(self, item: AgenteWhatsAppOutbox) -> dict[str, Any]:
        return {
            "id": item.id,
            "message_id": item.message_id,
            "session_id": item.session_id,
            "customer_id": item.customer_id,
            "phone": item.phone,
            "provider": item.provider,
            "message_type": item.message.message_type if item.message else None,
            "message_body": item.message.body if item.message else None,
            "status": item.status,
            "attempts": item.attempts,
            "max_attempts": item.max_attempts,
            "idempotency_key": item.idempotency_key,
            "provider_message_id": item.provider_message_id,
            "error": item.error,
            "next_attempt_at": item.next_attempt_at,
            "locked_at": item.locked_at,
            "sent_at": item.sent_at,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
        }

    def _process_item(self, item: AgenteWhatsAppOutbox) -> bool:
        now = _now_utc()
        provider = _normalize_provider(item.provider)
        if self._is_provider_paused(provider, now):
            return self._defer_item(item, f"Provider {provider} pausado pelo AGENTE WHATSAPP.")

        item.status = "processing"
        item.locked_at = now
        item.attempts = (item.attempts or 0) + 1
        item.updated_at = now
        self._db.flush()

        message = item.message
        if not message:
            return self._fail_item(item, "Mensagem da fila nao encontrada.")
        if message.provider_status == "sent" and message.provider_message_id:
            item.status = "sent"
            item.provider_message_id = message.provider_message_id
            item.sent_at = message.created_at or now
            item.error = None
            item.updated_at = now
            self._record_provider_success(provider)
            return True

        if provider == "qr":
            return self._fail_item(item, "WhatsApp QR Code ainda nao possui worker ativo.")
        if provider not in {"official", "evolution"}:
            return self._fail_item(item, "Provedor WhatsApp invalido.")

        payload = _json_load(item.payload_json)
        body = message.body or payload.get("body") or ""
        media_url = message.media_url or payload.get("media_url")
        media_type = _normalize_media_type(message.message_type, media_url)

        if provider == "evolution":
            cfg = _get_config(self._db)
            provider_message_id, status, error = _send_evolution_api(
                item.phone,
                body,
                cfg,
                media_type=media_type,
                media_url=media_url,
                caption=body if media_url else None,
            )
        else:
            provider_message_id, status, error = _send_whatsapp_api(
                item.phone,
                body,
                self._db,
                media_type=media_type,
                media_url=media_url,
                caption=body if media_url else None,
            )

        if status == "sent":
            message.provider_status = "sent"
            message.provider_message_id = provider_message_id
            message.error = None
            item.status = "sent"
            item.provider_message_id = provider_message_id
            item.error = None
            item.sent_at = _now_utc()
            item.locked_at = None
            item.updated_at = item.sent_at
            self._record_provider_success(provider)
            return True

        return self._fail_item(item, error or "Falha ao enviar mensagem WhatsApp.")

    def _ensure_provider_state(self, provider: str) -> AgenteWhatsAppProviderState:
        normalized = _normalize_provider(provider)
        state = (
            self._db.query(AgenteWhatsAppProviderState)
            .filter(AgenteWhatsAppProviderState.provider == normalized)
            .first()
        )
        if state:
            return state
        now = _now_utc()
        state = AgenteWhatsAppProviderState(
            id=str(uuid.uuid4()),
            provider=normalized,
            status="active",
            consecutive_failures=0,
            failure_threshold=max(1, self._settings.AGENTE_WHATSAPP_PROVIDER_FAILURE_THRESHOLD),
            created_at=now,
            updated_at=now,
        )
        self._db.add(state)
        self._db.flush()
        return state

    def _is_provider_paused(self, provider: str, now: datetime) -> bool:
        state = self._ensure_provider_state(provider)
        if state.status != "paused":
            return False
        if _is_due(state.paused_until, now):
            self.resume_provider(provider)
            return False
        return True

    def _record_provider_success(self, provider: str) -> None:
        state = self._ensure_provider_state(provider)
        now = _now_utc()
        state.status = "active"
        state.consecutive_failures = 0
        state.last_success_at = now
        state.paused_at = None
        state.paused_until = None
        state.paused_reason = None
        state.updated_at = now

    def _record_provider_failure(self, provider: str, error: str) -> None:
        state = self._ensure_provider_state(provider)
        now = _now_utc()
        threshold = max(1, self._settings.AGENTE_WHATSAPP_PROVIDER_FAILURE_THRESHOLD)
        state.failure_threshold = threshold
        state.consecutive_failures = (state.consecutive_failures or 0) + 1
        state.last_failure_at = now
        state.updated_at = now
        if state.consecutive_failures >= threshold:
            pause_minutes = max(1, self._settings.AGENTE_WHATSAPP_PROVIDER_PAUSE_MINUTES)
            state.status = "paused"
            state.paused_at = now
            state.paused_until = now + timedelta(minutes=pause_minutes)
            state.paused_reason = f"{state.consecutive_failures} falhas consecutivas. Ultimo erro: {error}"
            self.sync_internal_alerts()

    def _defer_item(self, item: AgenteWhatsAppOutbox, error: str) -> bool:
        now = _now_utc()
        state = self._ensure_provider_state(item.provider)
        item.status = "failed"
        item.error = error
        item.locked_at = None
        item.next_attempt_at = state.paused_until or (now + timedelta(minutes=5))
        item.updated_at = now
        if item.message:
            item.message.provider_status = "queued"
            item.message.error = error
        return False

    def _fail_item(self, item: AgenteWhatsAppOutbox, error: str) -> bool:
        now = _now_utc()
        provider = _normalize_provider(item.provider)
        item.error = error
        item.locked_at = None
        item.updated_at = now
        if item.attempts >= item.max_attempts:
            item.status = "dead"
            next_attempt = None
        else:
            item.status = "failed"
            next_attempt = now + timedelta(minutes=min(30, 2 ** max(item.attempts - 1, 0)))
        item.next_attempt_at = next_attempt
        if item.message:
            item.message.provider_status = "failed" if item.status == "dead" else "queued"
            item.message.error = error
        self._record_provider_failure(provider, error)
        return False
