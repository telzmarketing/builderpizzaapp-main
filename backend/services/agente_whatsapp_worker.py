from __future__ import annotations

import asyncio
import logging
from typing import Callable

from sqlalchemy.orm import Session

from backend.services.agente_whatsapp_outbox_service import AgenteWhatsAppOutboxService
from backend.services.agente_whatsapp_processing_service import AgenteWhatsAppProcessingService
from backend.services.agente_whatsapp_retention_service import AgenteWhatsAppRetentionService
from backend.services.agente_whatsapp_service import AgenteWhatsAppService

logger = logging.getLogger("agente_whatsapp.worker")


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
    logger.info("AGENTE WHATSAPP outbox worker started interval=%ss batch=%s", interval, limit)

    try:
        while True:
            try:
                with session_factory() as db:
                    agente_service = AgenteWhatsAppService(db)
                    scheduled = agente_service.process_scheduled_campaigns(limit=10)
                    scheduled_stories = agente_service.process_scheduled_stories(limit=10)
                    commercial_automations = agente_service.run_due_commercial_automations(limit_per_automation=10)
                    processing_service = AgenteWhatsAppProcessingService(db)
                    audio_transcriptions = processing_service.process_audio_transcriptions(limit=5)
                    agent_responses = processing_service.process_agent_responses(limit=5)
                    tts_generations = processing_service.process_tts_generations(limit=5)
                    retention_service = AgenteWhatsAppRetentionService(db)
                    retention_cleanup = (
                        retention_service.audio_cleanup(dry_run=False)
                        if retention_service.should_run_automatic_cleanup()
                        else {"eligible": 0, "deleted_files": 0}
                    )
                    service = AgenteWhatsAppOutboxService(db)
                    result = service.process_pending(limit=limit)
                    service.sync_internal_alerts()
                    db.commit()
                    if (
                        result.get("processed")
                        or result.get("enqueued")
                        or scheduled.get("processed")
                        or scheduled_stories.get("processed")
                        or commercial_automations.get("queued")
                        or audio_transcriptions.get("processed")
                        or agent_responses.get("processed")
                        or tts_generations.get("processed")
                        or retention_cleanup.get("deleted_files")
                    ):
                        logger.info(
                            "AGENTE WHATSAPP outbox worker cycle result=%s scheduled=%s stories=%s automations=%s audio=%s responses=%s tts=%s retention=%s",
                            result,
                            scheduled,
                            scheduled_stories,
                            commercial_automations,
                            audio_transcriptions,
                            agent_responses,
                            tts_generations,
                            retention_cleanup,
                        )
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("AGENTE WHATSAPP outbox worker cycle failed")

            await asyncio.sleep(interval)
    finally:
        logger.info("AGENTE WHATSAPP outbox worker stopped")
