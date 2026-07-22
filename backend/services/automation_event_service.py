"""Tenant-isolated event ingestion, matching and idempotent materialization."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.schemas.automation_core import AutomationSimulationInput
from backend.services.automation_registry import conditions_match, validate_definition


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AutomationEventService:
    def __init__(self, db: Session, tenant_id: str):
        if not tenant_id:
            raise ValueError("tenant_id obrigatorio")
        self.db, self.tenant_id = db, tenant_id

    def publish(self, *, event_key: str, aggregate_type: str, aggregate_id: str,
                dedupe_key: str, payload: dict[str, Any], customer_id: str | None = None,
                correlation_id: str | None = None, causation_id: str | None = None) -> str:
        if not dedupe_key:
            raise ValueError("dedupe_key obrigatorio")
        event_id, now = str(uuid.uuid4()), _now()
        row = self.db.execute(text("""
            INSERT INTO automation_events (
                id, tenant_id, event_key, event_version, aggregate_type, aggregate_id,
                customer_id, payload_json, occurred_at, available_at, status, attempts,
                max_attempts, correlation_id, causation_id, dedupe_key, created_at, updated_at
            ) VALUES (:id,:tenant_id,:event_key,1,:aggregate_type,:aggregate_id,
                :customer_id,:payload_json,:now,:now,'pending',0,5,
                :correlation_id,:causation_id,:dedupe_key,:now,:now)
            ON CONFLICT (tenant_id, dedupe_key) DO NOTHING RETURNING id
        """), {"id": event_id, "tenant_id": self.tenant_id, "event_key": event_key,
                "aggregate_type": aggregate_type, "aggregate_id": aggregate_id,
                "customer_id": customer_id, "payload_json": json.dumps(payload, ensure_ascii=False),
                "correlation_id": correlation_id, "causation_id": causation_id,
                "dedupe_key": dedupe_key, "now": now}).fetchone()
        if row:
            return row[0]
        return str(self.db.execute(text(
            "SELECT id FROM automation_events WHERE tenant_id=:tenant_id AND dedupe_key=:dedupe_key"
        ), {"tenant_id": self.tenant_id, "dedupe_key": dedupe_key}).scalar())

    def simulate(self, body: AutomationSimulationInput) -> dict[str, Any]:
        validation = validate_definition(body)
        payload = dict(body.sample_payload)
        if body.sample_event_id:
            row = self.db.execute(text(
                "SELECT event_key,payload_json FROM automation_events WHERE id=:id AND tenant_id=:tenant_id"
            ), {"id": body.sample_event_id, "tenant_id": self.tenant_id}).fetchone()
            if not row:
                validation["errors"].append({"path": "sample_event_id", "code": "not_found", "message": "Evento de exemplo nao encontrado neste tenant."})
                validation["valid"] = False
            else:
                payload = json.loads(row[1] or "{}")
                if row[0] != body.trigger.key:
                    validation["warnings"].append({"path": "sample_event_id", "code": "trigger_mismatch", "message": "Evento de exemplo tem outro gatilho."})
        trigger_match = validation["valid"]
        condition_match, steps = conditions_match(body.conditions, payload)
        matched = trigger_match and condition_match
        return {"matched": matched, "would_execute": [a.model_dump() for a in body.actions] if matched else [],
                "steps": [{"type": "trigger", "key": body.trigger.key, "matched": trigger_match}, *steps],
                "warnings": validation["warnings"], "errors": validation["errors"]}

    def process_pending(self, *, limit: int = 25, worker_id: str = "automation-worker") -> dict[str, int]:
        now, lease_cutoff = _now(), _now() - timedelta(minutes=5)
        events = self.db.execute(text("""
            WITH candidates AS (
                SELECT id FROM automation_events WHERE tenant_id=:tenant_id AND available_at<=:now
                  AND (status IN ('pending','failed') OR (status='processing' AND locked_at<:lease_cutoff))
                  AND attempts<max_attempts ORDER BY available_at,occurred_at
                  FOR UPDATE SKIP LOCKED LIMIT :limit)
            UPDATE automation_events e SET status='processing',locked_at=:now,
                locked_by=:worker_id,attempts=e.attempts+1,updated_at=:now
            FROM candidates c WHERE e.id=c.id
            RETURNING e.id,e.event_key,e.aggregate_type,e.aggregate_id,e.customer_id,
                      e.payload_json,e.attempts,e.max_attempts
        """), {"tenant_id": self.tenant_id, "now": now, "lease_cutoff": lease_cutoff,
                "worker_id": worker_id, "limit": limit}).fetchall()
        self.db.commit()
        counts = {"claimed": len(events), "processed": 0, "failed": 0, "executions_created": 0}
        for event in events:
            try:
                counts["executions_created"] += self._materialize_event(event)
                self.db.execute(text("""UPDATE automation_events SET status='processed',processed_at=:now,
                    locked_at=NULL,locked_by=NULL,last_error=NULL,updated_at=:now
                    WHERE id=:id AND tenant_id=:tenant_id"""),
                    {"id": event[0], "tenant_id": self.tenant_id, "now": _now()})
                self.db.commit(); counts["processed"] += 1
            except Exception as exc:
                self.db.rollback()
                terminal = event[6] >= event[7]
                self.db.execute(text("""UPDATE automation_events SET status=:status,last_error=:error,
                    available_at=:available_at,locked_at=NULL,locked_by=NULL,updated_at=:now
                    WHERE id=:id AND tenant_id=:tenant_id"""),
                    {"id": event[0], "tenant_id": self.tenant_id, "status": "dead" if terminal else "failed",
                     "error": str(exc)[:4000], "available_at": _now()+timedelta(minutes=min(60, 2**event[6])), "now": _now()})
                self.db.commit(); counts["failed"] += 1
        return counts

    def _materialize_event(self, event: Any) -> int:
        event_id,event_key,aggregate_type,aggregate_id,customer_id,payload_raw,_,_ = event
        payload = json.loads(payload_raw or "{}")
        rows = self.db.execute(text("""SELECT id,conditions_json,actions_json FROM marketing_automations
            WHERE tenant_id=:tenant_id AND active=TRUE AND trigger=:event_key"""),
            {"tenant_id": self.tenant_id, "event_key": event_key}).fetchall()
        created = 0
        for automation_id, conditions_raw, actions_raw in rows:
            definition = AutomationSimulationInput(trigger={"key":event_key,"config":{}},
                conditions=json.loads(conditions_raw or "[]"), actions=json.loads(actions_raw or "[]"),
                sample_payload=payload)
            valid = validate_definition(definition)
            matched, _ = conditions_match(definition.conditions, payload)
            if not valid["valid"] or not matched:
                continue
            for index, action in enumerate(definition.actions):
                dedupe = f"{self.tenant_id}:{automation_id}:{event_id}:{index}:{aggregate_id or customer_id or '-'}"
                result = self.db.execute(text("""INSERT INTO automation_executions (
                    id,tenant_id,automation_id,customer_id,trigger_event_id,source_event_type,
                    channel,status,scheduled_at,attempts,max_attempts,dedupe_key,message_body,
                    metadata_json,created_at,updated_at)
                    VALUES (:id,:tenant_id,:automation_id,:customer_id,:event_id,:event_key,:channel,
                    'pending',:now,0,3,:dedupe_key,:message_body,:metadata_json,:now,:now)
                    ON CONFLICT (tenant_id,dedupe_key) DO NOTHING RETURNING id"""),
                    {"id":str(uuid.uuid4()),"tenant_id":self.tenant_id,"automation_id":automation_id,
                     "customer_id":customer_id,"event_id":event_id,"event_key":event_key,"channel":"workflow",
                     "dedupe_key":dedupe,"message_body":action.config.get("message"),
                     "metadata_json":json.dumps({"action_key":action.key,"action_config":action.config,
                        "aggregate_type":aggregate_type,"aggregate_id":aggregate_id}, ensure_ascii=False),"now":_now()}).fetchone()
                created += int(result is not None)
        return created
