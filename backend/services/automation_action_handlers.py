"""Safe executors for the transversal automation action whitelist."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.services.automation_registry import ACTIONS


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ActionHandlerRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, Callable[..., tuple[str, str | None, str | None]]] = {
            "crm.assign_tag": self._assign_tag,
            "crm.create_task": self._create_task,
            "notification.send_whatsapp": self._send_whatsapp,
            "notification.send_email": self._send_email,
        }

    def execute(self, db: Session, tenant_id: str, execution: dict[str, Any]) -> tuple[str, str | None, str | None]:
        metadata = json.loads(execution.get("metadata_json") or "{}")
        action_key = metadata.get("action_key")
        config = metadata.get("action_config") or {}
        if action_key not in ACTIONS or action_key not in self._handlers:
            return "failed", "Acao fora do registry permitido.", None
        return self._handlers[action_key](db, tenant_id, execution, config)

    @staticmethod
    def _require_customer(execution: dict[str, Any]) -> str:
        customer_id = execution.get("customer_id")
        if not customer_id:
            raise ValueError("Acao exige customer_id.")
        return customer_id

    def _assign_tag(self, db: Session, tenant_id: str, execution: dict[str, Any], config: dict[str, Any]):
        customer_id, tag_id = self._require_customer(execution), str(config.get("tag_id") or "")
        valid = db.execute(text("""SELECT 1 FROM customer_tags t JOIN customers c ON c.id=:customer_id
            AND c.tenant_id=:tenant_id WHERE t.id=:tag_id AND t.tenant_id=:tenant_id AND t.status='active'"""),
            {"tenant_id": tenant_id, "customer_id": customer_id, "tag_id": tag_id}).scalar()
        if not valid:
            return "failed", "Cliente ou tag nao encontrado neste tenant.", None
        assignment_id = str(uuid.uuid4())
        inserted = db.execute(text("""INSERT INTO customer_tag_assignments
            (id,tenant_id,customer_id,tag_id,source,created_by,created_at)
            VALUES (:id,:tenant_id,:customer_id,:tag_id,'automation','automation-core',:now)
            ON CONFLICT (tenant_id,customer_id,tag_id) DO NOTHING RETURNING id"""),
            {"id": assignment_id, "tenant_id": tenant_id, "customer_id": customer_id, "tag_id": tag_id, "now": _now()}).scalar()
        if inserted:
            from types import SimpleNamespace
            from backend.services.automation_event_producer import AutomationEventProducer
            AutomationEventProducer(db, tenant_id).customer_tag_assigned(SimpleNamespace(
                id=assignment_id, tenant_id=tenant_id, customer_id=customer_id,
                tag_id=tag_id, source="automation"
            ))
        return "completed", None, None

    def _create_task(self, db: Session, tenant_id: str, execution: dict[str, Any], config: dict[str, Any]):
        customer_id = self._require_customer(execution)
        valid = db.execute(text("SELECT 1 FROM customers WHERE id=:id AND tenant_id=:tenant_id"),
                           {"id": customer_id, "tenant_id": tenant_id}).scalar()
        if not valid:
            return "failed", "Cliente nao encontrado neste tenant.", None
        db.execute(text("""INSERT INTO crm_tasks
            (id,tenant_id,customer_id,title,description,task_type,responsible,due_date,priority,status,created_at,updated_at)
            VALUES (:id,:tenant_id,:customer_id,:title,:description,:task_type,:responsible,NULL,:priority,'pending',:now,:now)"""),
            {"id": str(uuid.uuid4()), "tenant_id": tenant_id, "customer_id": customer_id,
             "title": str(config.get("title") or "")[:300], "description": config.get("description"),
             "task_type": str(config.get("task_type") or "other")[:50], "responsible": config.get("responsible"),
             "priority": str(config.get("priority") or "medium")[:20], "now": _now()})
        return "completed", None, None

    def _notification(self, db: Session, tenant_id: str, execution: dict[str, Any], config: dict[str, Any], channel: str):
        from backend.services.automation_service import customer_allows_channel, send_message
        from backend.services.customer_contact_risk_service import CustomerContactRiskService

        customer_id = self._require_customer(execution)
        row = db.execute(text("""SELECT id,name,phone,email,marketing_whatsapp_consent,marketing_email_consent
            FROM customers WHERE id=:id AND tenant_id=:tenant_id"""),
            {"id": customer_id, "tenant_id": tenant_id}).mappings().first()
        if not row:
            return "failed", "Cliente nao encontrado neste tenant.", None
        customer = dict(row)
        allowed, reason = customer_allows_channel(customer, channel)
        risk_service = None
        if allowed and channel == "whatsapp":
            risk_service = CustomerContactRiskService(db, tenant_id)
            eligibility = risk_service.evaluate_whatsapp_marketing(customer_id=customer_id, phone=customer.get("phone") or "")
            allowed, reason = eligibility.allowed, eligibility.reason
        if not allowed:
            return "cancelled", reason, None
        automation = {"channel": channel, "template_id": None}
        status, error, provider_id = send_message(db, automation, customer,
            str(config.get("subject") or "") or None, str(config.get("message") or ""))
        if status == "sent" and risk_service:
            risk_service.record_campaign_sent(customer_id, source_type="automation_execution", source_id=execution["execution_id"])
        return status, error, provider_id

    def _send_whatsapp(self, db: Session, tenant_id: str, execution: dict[str, Any], config: dict[str, Any]):
        return self._notification(db, tenant_id, execution, config, "whatsapp")

    def _send_email(self, db: Session, tenant_id: str, execution: dict[str, Any], config: dict[str, Any]):
        return self._notification(db, tenant_id, execution, config, "email")


def process_transversal_executions(db: Session, tenant_id: str, limit: int = 100, worker_id: str = "automation-action-worker") -> dict[str, int]:
    """Claim and execute only records produced by the transversal event core."""
    rows = db.execute(text("""WITH candidates AS (
        SELECT id FROM automation_executions WHERE tenant_id=:tenant_id
          AND (status='pending' OR (status='processing' AND locked_at<:lease_cutoff))
          AND scheduled_at<=:now AND attempts<max_attempts AND metadata_json LIKE '%\"action_key\"%'
        ORDER BY scheduled_at,created_at FOR UPDATE SKIP LOCKED LIMIT :limit)
        UPDATE automation_executions e SET status='processing',started_at=COALESCE(e.started_at,:now),
          attempts=e.attempts+1,locked_at=:now,locked_by=:worker_id,updated_at=:now
        FROM candidates c WHERE e.id=c.id
        RETURNING e.id AS execution_id,e.automation_id,e.customer_id,e.metadata_json,e.attempts,e.max_attempts"""),
        {"tenant_id": tenant_id, "now": _now(), "lease_cutoff": _now()-timedelta(minutes=5), "worker_id": worker_id, "limit": limit}).mappings().all()
    db.commit()
    registry, totals = ActionHandlerRegistry(), {"claimed": len(rows), "completed": 0, "sent": 0, "failed": 0, "cancelled": 0, "retried": 0}
    for raw in rows:
        execution = dict(raw)
        try:
            status, error, provider_id = registry.execute(db, tenant_id, execution)
            final_status = "sent" if status == "sent" else ("completed" if status == "completed" else status)
            db.execute(text("""UPDATE automation_executions SET status=:status,error=:error,
                provider_message_id=:provider_id,finished_at=:now,sent_at=CASE WHEN :status='sent' THEN :now ELSE sent_at END,
                locked_at=NULL,locked_by=NULL,updated_at=:now WHERE id=:id AND tenant_id=:tenant_id"""),
                {"status": final_status, "error": error, "provider_id": provider_id, "now": _now(),
                 "id": execution["execution_id"], "tenant_id": tenant_id})
            db.commit()
            totals[final_status if final_status in totals else "failed"] += 1
        except Exception as exc:
            db.rollback()
            retry = int(execution.get("attempts") or 0) < int(execution.get("max_attempts") or 3)
            db.execute(text("""UPDATE automation_executions SET status=:status,error=:error,
                scheduled_at=:scheduled_at,finished_at=CASE WHEN :status='failed' THEN :now ELSE NULL END,
                locked_at=NULL,locked_by=NULL,updated_at=:now WHERE id=:id AND tenant_id=:tenant_id"""),
                {"status": "pending" if retry else "failed", "error": str(exc)[:4000],
                 "scheduled_at": _now()+timedelta(minutes=min(60,2**int(execution.get("attempts") or 1))),
                 "now": _now(), "id": execution["execution_id"], "tenant_id": tenant_id})
            db.commit(); totals["retried" if retry else "failed"] += 1
    return totals
