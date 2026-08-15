"""Cross-tenant, payload-free operational queue projection."""
from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import text

from backend.services.platform_operations_common import (
    parse_datetime,
    safe_identifier,
    safe_label,
    utcnow,
)


QUEUE_LABELS = {
    "automation_events": "Eventos de automacao",
    "automation_executions": "Execucoes de automacao",
    "whatsapp_processing": "Processamento WhatsApp",
    "whatsapp_outbox": "Saida WhatsApp",
    "customer_ai": "Analise de clientes",
}


JOBS_CTE = """
WITH raw_jobs AS (
    SELECT e.id, e.tenant_id, 'automation_events'::text AS queue_key,
           e.event_key::text AS job_type, e.status::text AS source_status,
           e.attempts, e.max_attempts, e.created_at,
           e.available_at AS scheduled_at, e.available_at AS next_attempt_at,
           e.locked_at, e.updated_at, e.processed_at AS finished_at,
           (e.last_error IS NOT NULL) AS error_present
      FROM automation_events e
     WHERE e.tenant_id IS NOT NULL
    UNION ALL
    SELECT e.id, e.tenant_id, 'automation_executions'::text,
           COALESCE(e.source_event_type, e.channel, 'automation')::text,
           e.status::text, e.attempts, e.max_attempts, e.created_at,
           e.scheduled_at, e.next_attempt_at, e.locked_at, e.updated_at,
           COALESCE(e.finished_at, e.sent_at), (e.error IS NOT NULL)
      FROM automation_executions e
     WHERE e.tenant_id IS NOT NULL
    UNION ALL
    SELECT j.id, j.tenant_id, 'whatsapp_processing'::text,
           j.job_type::text, j.status::text, j.attempts, j.max_attempts,
           j.created_at, j.created_at, j.next_attempt_at, j.locked_at,
           j.updated_at, j.finished_at, (j.error IS NOT NULL)
      FROM agente_whatsapp_processing_jobs j
     WHERE j.tenant_id IS NOT NULL
    UNION ALL
    SELECT o.id, o.tenant_id, 'whatsapp_outbox'::text,
           COALESCE(o.provider, 'outbox')::text, o.status::text,
           o.attempts, o.max_attempts, o.created_at, o.created_at,
           o.next_attempt_at, o.locked_at, o.updated_at, o.sent_at,
           (o.error IS NOT NULL)
      FROM agente_whatsapp_outbox o
     WHERE o.tenant_id IS NOT NULL
    UNION ALL
    SELECT a.id, a.tenant_id, 'customer_ai'::text, 'customer_analysis'::text,
           a.status::text, 0, 1, a.created_at, a.created_at, NULL,
           a.started_at, a.updated_at, a.finished_at,
           (a.error_message IS NOT NULL)
      FROM customer_ai_analysis_jobs a
     WHERE a.tenant_id IS NOT NULL
), jobs AS (
    SELECT raw_jobs.*,
           CASE
             WHEN source_status IN ('pending','queued','created') THEN 'queued'
             WHEN source_status IN ('processing','running','sending','in_progress') THEN 'running'
             WHEN source_status IN ('processed','sent','completed','success','succeeded') THEN 'succeeded'
             WHEN source_status IN ('dead','exhausted') THEN 'dead'
             WHEN source_status IN ('cancelled','canceled','skipped') THEN 'cancelled'
             WHEN source_status IN ('failed','error') AND attempts < max_attempts THEN 'retrying'
             WHEN source_status IN ('failed','error') THEN 'failed'
             ELSE 'unknown'
           END AS normalized_status
      FROM raw_jobs
      JOIN tenants active_tenant
        ON active_tenant.id = raw_jobs.tenant_id
       AND active_tenant.deleted_at IS NULL
)
"""


FILTERS = """
WHERE (:tenant_id IS NULL OR jobs.tenant_id = :tenant_id)
  AND (:queue_key IS NULL OR jobs.queue_key = :queue_key)
  AND (:job_status IS NULL OR jobs.normalized_status = :job_status)
"""


class PlatformJobsService:
    def __init__(self, db):
        self.db = db

    @staticmethod
    def _params(*, tenant_id=None, queue_key=None, status=None) -> dict:
        return {
            "tenant_id": tenant_id,
            "queue_key": queue_key,
            "job_status": status,
        }

    def record_heartbeat(
        self, *, worker_key: str, instance_key: str, queue_key: str,
        status: str = "running", tenant_id: str | None = None,
        version: str | None = None,
    ) -> None:
        """Upsert liveness from a trusted worker; this method is not an HTTP action."""
        worker = safe_identifier(worker_key, default="")
        instance = safe_identifier(instance_key, default="", max_length=120)
        queue = safe_identifier(queue_key, default="")
        normalized_status = safe_identifier(status)
        if not worker or not instance or not queue:
            raise ValueError("worker_key, instance_key e queue_key sao obrigatorios")
        if normalized_status not in {"running", "idle", "degraded", "stopped"}:
            raise ValueError("status de worker invalido")
        now = utcnow()
        self.db.execute(text("""
            INSERT INTO platform_worker_heartbeats (
                id, tenant_id, worker_key, instance_key, queue_key, status,
                version, started_at, last_heartbeat_at, created_at, updated_at
            ) VALUES (
                :id, :tenant_id, :worker_key, :instance_key, :queue_key, :status,
                :version, :now, :now, :now, :now
            )
            ON CONFLICT (worker_key, instance_key) DO UPDATE SET
                tenant_id = EXCLUDED.tenant_id,
                queue_key = EXCLUDED.queue_key,
                status = EXCLUDED.status,
                version = EXCLUDED.version,
                last_heartbeat_at = EXCLUDED.last_heartbeat_at,
                updated_at = EXCLUDED.updated_at
        """), {
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "worker_key": worker,
            "instance_key": instance,
            "queue_key": queue,
            "status": normalized_status,
            "version": safe_label(version, default="", max_length=80) or None,
            "now": now,
        })
        self.db.commit()

    def _workers(self) -> list[dict]:
        rows = self.db.execute(text("""
            SELECT worker_key, instance_key, status, last_heartbeat_at
              FROM platform_worker_heartbeats
             ORDER BY worker_key, instance_key
        """)).mappings().all()
        now = utcnow()
        result: list[dict] = []
        for source in rows:
            row = dict(source)
            seen = parse_datetime(row.get("last_heartbeat_at"))
            age = (now - seen).total_seconds() if seen else float("inf")
            source_status = safe_identifier(row.get("status"))
            if source_status == "stopped" or age > 600:
                health = "critical"
            elif source_status == "degraded" or age > 120:
                health = "degraded"
            elif source_status in {"running", "idle"}:
                health = "healthy"
            else:
                health = "unknown"
            result.append({
                "key": safe_identifier(row.get("worker_key")),
                "instance_key": safe_identifier(
                    row.get("instance_key"), max_length=120
                ),
                "status": health,
                "last_heartbeat_at": seen,
                "stale": age > 120,
            })
        return result

    def overview(self) -> dict:
        row = self.db.execute(text(JOBS_CTE + """
            SELECT count(*) AS total,
                   count(*) FILTER (WHERE normalized_status='queued') AS queued,
                   count(*) FILTER (WHERE normalized_status='running') AS running,
                   count(*) FILTER (WHERE normalized_status='retrying') AS retrying,
                   count(*) FILTER (WHERE normalized_status='succeeded') AS succeeded,
                   count(*) FILTER (WHERE normalized_status='failed') AS failed,
                   count(*) FILTER (WHERE normalized_status='dead') AS dead,
                   min(COALESCE(next_attempt_at, scheduled_at, created_at))
                     FILTER (WHERE normalized_status IN ('queued','retrying')) AS oldest_pending_at
              FROM jobs
        """)).mappings().one()
        return {
            "total": int(row["total"] or 0),
            "queued": int(row["queued"] or 0),
            "running": int(row["running"] or 0),
            "retrying": int(row["retrying"] or 0),
            "succeeded": int(row["succeeded"] or 0),
            "failed": int(row["failed"] or 0),
            "dead": int(row["dead"] or 0),
            "oldest_pending_at": parse_datetime(row["oldest_pending_at"]),
            "workers": self._workers(),
            "generated_at": utcnow(),
        }

    def queues(self) -> dict:
        rows = self.db.execute(text(JOBS_CTE + """
            SELECT queue_key, count(*) AS total,
                   count(*) FILTER (WHERE normalized_status='queued') AS queued,
                   count(*) FILTER (WHERE normalized_status='running') AS running,
                   count(*) FILTER (WHERE normalized_status='retrying') AS retrying,
                   count(*) FILTER (WHERE normalized_status='succeeded') AS succeeded,
                   count(*) FILTER (WHERE normalized_status='failed') AS failed,
                   count(*) FILTER (WHERE normalized_status='dead') AS dead,
                   min(COALESCE(next_attempt_at, scheduled_at, created_at))
                     FILTER (WHERE normalized_status IN ('queued','retrying')) AS oldest_pending_at
              FROM jobs GROUP BY queue_key ORDER BY queue_key
        """)).mappings().all()
        by_key = {row["queue_key"]: row for row in rows}
        items = []
        for key, label in QUEUE_LABELS.items():
            row = by_key.get(key, {})
            items.append({
                "key": key,
                "label": label,
                "total": int(row.get("total") or 0),
                "queued": int(row.get("queued") or 0),
                "running": int(row.get("running") or 0),
                "retrying": int(row.get("retrying") or 0),
                "succeeded": int(row.get("succeeded") or 0),
                "failed": int(row.get("failed") or 0),
                "dead": int(row.get("dead") or 0),
                "oldest_pending_at": parse_datetime(row.get("oldest_pending_at")),
            })
        return {"items": items, "generated_at": utcnow()}

    def list_items(
        self, *, page: int, page_size: int, tenant_id: str | None = None,
        queue_key: str | None = None, status: str | None = None,
        age_minutes: int | None = None,
    ) -> dict:
        params = self._params(tenant_id=tenant_id, queue_key=queue_key, status=status)
        params.update({
            "offset": (page - 1) * page_size,
            "limit": page_size,
            "age_cutoff": utcnow() - timedelta(minutes=age_minutes) if age_minutes is not None else None,
        })
        age_filter = " AND (:age_cutoff IS NULL OR jobs.created_at <= :age_cutoff)"
        total = self.db.execute(text(
            JOBS_CTE + "SELECT count(*) FROM jobs " + FILTERS + age_filter
        ), params).scalar_one()
        rows = self.db.execute(text(JOBS_CTE + """
            SELECT jobs.*, t.name AS tenant_name
              FROM jobs
              JOIN tenants t ON t.id = jobs.tenant_id AND t.deleted_at IS NULL
        """ + FILTERS + age_filter + """
             ORDER BY COALESCE(jobs.updated_at, jobs.created_at) DESC, jobs.id
             OFFSET :offset LIMIT :limit
        """), params).mappings().all()
        now = utcnow()
        items = []
        for source in rows:
            row = dict(source)
            created_at = parse_datetime(row.get("created_at"))
            items.append({
                "id": safe_label(row.get("id"), max_length=180),
                "tenant": {
                    "id": safe_label(row.get("tenant_id"), max_length=100),
                    "name": safe_label(row.get("tenant_name"), max_length=200),
                },
                "queue": safe_identifier(row.get("queue_key")),
                "job_type": safe_identifier(row.get("job_type")),
                "status": safe_identifier(row.get("normalized_status")),
                "source_status": safe_identifier(row.get("source_status")),
                "attempts": max(0, int(row.get("attempts") or 0)),
                "max_attempts": max(0, int(row.get("max_attempts") or 0)),
                "created_at": created_at,
                "scheduled_at": parse_datetime(row.get("scheduled_at")),
                "next_attempt_at": parse_datetime(row.get("next_attempt_at")),
                "locked_at": parse_datetime(row.get("locked_at")),
                "updated_at": parse_datetime(row.get("updated_at")),
                "finished_at": parse_datetime(row.get("finished_at")),
                "age_seconds": max(0, int((now - created_at).total_seconds())) if created_at else 0,
                "error_present": bool(row.get("error_present")),
            })
        return {"items": items, "page": page, "page_size": page_size, "total": int(total or 0)}
