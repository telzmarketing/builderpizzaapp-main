from __future__ import annotations

import asyncio
import logging
from typing import Callable

from sqlalchemy.orm import Session

from backend.services.agente_whatsapp_outbox_service import AgenteWhatsAppOutboxService

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
                    service = AgenteWhatsAppOutboxService(db)
                    result = service.process_pending(limit=limit)
                    service.sync_internal_alerts()
                    db.commit()
                    if result.get("processed") or result.get("enqueued"):
                        logger.info("AGENTE WHATSAPP outbox worker cycle result=%s", result)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("AGENTE WHATSAPP outbox worker cycle failed")

            await asyncio.sleep(interval)
    finally:
        logger.info("AGENTE WHATSAPP outbox worker stopped")
