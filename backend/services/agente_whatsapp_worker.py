from __future__ import annotations

import asyncio
import logging
import os
import socket
from typing import Callable

from sqlalchemy.orm import Session

from backend.core.tenant_context import TenantSource, trusted_process_context
from backend.core.wave6_tenant_context import bind_wave6_tenant_context
from backend.core.wave6_tenant_orm import wave6_tenant_orm_enabled
from backend.models.tenant import Tenant
from backend.services.agente_whatsapp_outbox_service import AgenteWhatsAppOutboxService
from backend.services.platform_jobs_service import PlatformJobsService
from backend.services.agente_whatsapp_processing_service import AgenteWhatsAppProcessingService
from backend.services.agente_whatsapp_retention_service import AgenteWhatsAppRetentionService
from backend.services.agente_whatsapp_service import AgenteWhatsAppService

logger = logging.getLogger("agente_whatsapp.worker")
WORKER_KEY = "agente_whatsapp_outbox"
QUEUE_KEY = "whatsapp_outbox"


def _worker_instance_key() -> str:
    return f"{socket.gethostname() or 'unknown'}:{os.getpid()}"


def _record_worker_heartbeat(
    session_factory: Callable[[], Session],
    *,
    instance_key: str,
    status: str,
) -> None:
    """Record liveness in an isolated transaction without affecting queue work."""
    try:
        with session_factory() as heartbeat_db:
            PlatformJobsService(heartbeat_db).record_heartbeat(
                worker_key=WORKER_KEY,
                instance_key=instance_key,
                queue_key=QUEUE_KEY,
                status=status,
            )
    except Exception:
        logger.warning("AGENTE WHATSAPP worker heartbeat failed status=%s", status, exc_info=True)


def _active_tenant_ids(db: Session) -> list[str]:
    """Return persisted active tenants; the worker never accepts a tenant from input."""
    return [
        tenant_id
        for (tenant_id,) in (
            db.query(Tenant.id)
            .filter(Tenant.status == "active", Tenant.deleted_at.is_(None))
            .order_by(Tenant.id.asc())
            .all()
        )
    ]


def _run_tenant_cycle(db: Session, *, tenant_id: str, limit: int) -> dict[str, object]:
    """Drain one tenant only, with its context bound before any Wave 6 write."""
    context = trusted_process_context(tenant_id, source=TenantSource.JOB)
    bind_wave6_tenant_context(db, context)

    agente_service = AgenteWhatsAppService(db, context)
    scheduled = agente_service.process_scheduled_campaigns(limit=10)
    scheduled_stories = agente_service.process_scheduled_stories(limit=10)
    commercial_automations = agente_service.run_due_commercial_automations(limit_per_automation=10)

    # Audio/AI/TTS services have their own remaining isolation delivery.  Do
    # not route a tenant worker through their legacy global data paths while
    # Wave 6 is on; report no work instead of risking a cross-tenant action.
    if wave6_tenant_orm_enabled():
        audio_transcriptions = {"processed": 0, "deferred": 1}
        agent_responses = {"processed": 0, "deferred": 1}
        tts_generations = {"processed": 0, "deferred": 1}
    else:
        processing_service = AgenteWhatsAppProcessingService(db, context)
        audio_transcriptions = processing_service.process_audio_transcriptions(limit=5)
        agent_responses = processing_service.process_agent_responses(limit=5)
        tts_generations = processing_service.process_tts_generations(limit=5)

    retention_service = AgenteWhatsAppRetentionService(db, context)
    retention_cleanup = (
        retention_service.audio_cleanup(dry_run=False)
        if retention_service.should_run_automatic_cleanup()
        else {"eligible": 0, "deleted_files": 0}
    )
    service = AgenteWhatsAppOutboxService(db, context)
    result = service.process_pending(limit=limit)
    service.sync_internal_alerts()
    return {
        "tenant_id": tenant_id,
        "outbox": result,
        "scheduled": scheduled,
        "stories": scheduled_stories,
        "automations": commercial_automations,
        "audio": audio_transcriptions,
        "responses": agent_responses,
        "tts": tts_generations,
        "retention": retention_cleanup,
    }


async def run_agente_whatsapp_outbox_worker(
    session_factory: Callable[[], Session],
    *,
    interval_seconds: int,
    batch_size: int,
) -> None:
    """Background worker that drains AGENTE WHATSAPP outbox.

    The queue source is PostgreSQL outbox, so it does not require a new Redis
    dependency to start operating. Row locking in the service prevents multiple
    workers from sending the same item at the same time.
    """

    interval = max(2, int(interval_seconds or 10))
    limit = max(1, min(int(batch_size or 20), 100))
    instance_key = _worker_instance_key()
    logger.info("AGENTE WHATSAPP outbox worker started interval=%ss batch=%s", interval, limit)

    try:
        while True:
            try:
                with session_factory() as db:
                    tenant_results = []
                    for tenant_id in _active_tenant_ids(db):
                        try:
                            tenant_result = _run_tenant_cycle(db, tenant_id=tenant_id, limit=limit)
                            db.commit()
                            tenant_results.append(tenant_result)
                        except Exception:
                            db.rollback()
                            logger.exception("AGENTE WHATSAPP tenant cycle failed tenant_id=%s", tenant_id)
                    did_work = any(bool((
                        item["outbox"].get("processed")
                        or item["outbox"].get("enqueued")
                        or item["scheduled"].get("processed")
                        or item["stories"].get("processed")
                        or item["automations"].get("queued")
                        or item["audio"].get("processed")
                        or item["responses"].get("processed")
                        or item["tts"].get("processed")
                        or item["retention"].get("deleted_files")
                    )) for item in tenant_results)
                    if did_work:
                        logger.info(
                            "AGENTE WHATSAPP worker tenant cycles=%s",
                            tenant_results,
                        )
                _record_worker_heartbeat(
                    session_factory,
                    instance_key=instance_key,
                    status="running" if did_work else "idle",
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("AGENTE WHATSAPP outbox worker cycle failed")
                _record_worker_heartbeat(
                    session_factory,
                    instance_key=instance_key,
                    status="degraded",
                )

            await asyncio.sleep(interval)
    finally:
        _record_worker_heartbeat(
            session_factory,
            instance_key=instance_key,
            status="stopped",
        )
        logger.info("AGENTE WHATSAPP outbox worker stopped")
