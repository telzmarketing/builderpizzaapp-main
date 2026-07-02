from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import or_
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.models.agente_whatsapp import AgenteWhatsAppMessage, AgenteWhatsAppProcessingJob
from backend.services.agente_whatsapp_audio_settings_service import AgenteWhatsAppAudioSettingsService
from backend.services.agente_whatsapp_audio_service import AgenteWhatsAppAudioService
from backend.services.agente_whatsapp_outbox_service import AgenteWhatsAppOutboxService
from backend.services.agente_whatsapp_rollout_service import AgenteWhatsAppRolloutService


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _json_dump(value: dict[str, Any] | None) -> str:
    return json.dumps(value or {}, ensure_ascii=False, default=str)


def _json_load(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        data = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


class AgenteWhatsAppProcessingService:
    def __init__(self, db: Session):
        self._db = db
        self._settings = get_settings()

    def enqueue_inbound_message(self, message: AgenteWhatsAppMessage) -> AgenteWhatsAppProcessingJob | None:
        if message.direction != "inbound":
            return None

        job_type = "audio_transcription" if message.message_type == "audio" else "inbound_message"
        if job_type == "audio_transcription" and not self._settings.WHATSAPP_AUDIO_INPUT_ENABLED:
            message.processing_status = "recorded"
            message.transcription_status = "none"
            self._db.flush()
            return None
        if job_type == "audio_transcription":
            allowed, reason = AgenteWhatsAppRolloutService(self._db).check_message(message, "audio_input")
            if not allowed:
                message.processing_status = "skipped"
                message.transcription_status = "none"
                message.transcription_error = reason
                self._db.flush()
                return None

        idempotency_key = f"{job_type}:{message.id}"
        existing = (
            self._db.query(AgenteWhatsAppProcessingJob)
            .filter(AgenteWhatsAppProcessingJob.idempotency_key == idempotency_key)
            .first()
        )
        if existing:
            if message.processing_status in {None, "", "recorded"}:
                message.processing_status = "queued"
            if message.message_type == "audio" and message.transcription_status in {None, "", "none"}:
                message.transcription_status = "pending"
            return existing

        now = _now_utc()
        if message.message_type == "audio" and message.transcription_status in {None, "", "none"}:
            message.transcription_status = "pending"
        job = AgenteWhatsAppProcessingJob(
            id=str(uuid.uuid4()),
            message_id=message.id,
            session_id=message.session_id,
            customer_id=message.customer_id,
            job_type=job_type,
            status="pending",
            attempts=0,
            max_attempts=3,
            idempotency_key=idempotency_key,
            payload_json=_json_dump(
                {
                    "message_id": message.id,
                    "session_id": message.session_id,
                    "message_type": message.message_type,
                    "provider": message.provider,
                    "provider_message_id": message.provider_message_id,
                    "quoted_provider_message_id": message.quoted_provider_message_id,
                    "campaign_id": message.campaign_id,
                    "campaign_delivery_id": message.campaign_delivery_id,
                }
            ),
            next_attempt_at=now,
            created_at=now,
            updated_at=now,
        )
        self._db.add(job)
        message.processing_status = "queued"
        self._db.flush()
        if message.message_type != "audio":
            self.enqueue_agent_response(message)
        return job

    def enqueue_agent_response(self, message: AgenteWhatsAppMessage) -> AgenteWhatsAppProcessingJob | None:
        if message.direction != "inbound":
            return None
        if message.message_type == "audio" and message.transcription_status not in {"done", "low_confidence"}:
            return None
        if self._existing_response(message.id):
            return None

        idempotency_key = f"agent_response:{message.id}"
        existing = (
            self._db.query(AgenteWhatsAppProcessingJob)
            .filter(AgenteWhatsAppProcessingJob.idempotency_key == idempotency_key)
            .first()
        )
        if existing:
            return existing

        now = _now_utc()
        job = AgenteWhatsAppProcessingJob(
            id=str(uuid.uuid4()),
            message_id=message.id,
            session_id=message.session_id,
            customer_id=message.customer_id,
            job_type="agent_response",
            status="pending",
            attempts=0,
            max_attempts=3,
            idempotency_key=idempotency_key,
            payload_json=_json_dump(
                {
                    "message_id": message.id,
                    "session_id": message.session_id,
                    "message_type": message.message_type,
                    "transcription_status": message.transcription_status,
                    "campaign_id": message.campaign_id,
                    "campaign_delivery_id": message.campaign_delivery_id,
                }
            ),
            next_attempt_at=now,
            created_at=now,
            updated_at=now,
        )
        self._db.add(job)
        self._db.flush()
        return job

    def enqueue_tts_generation(
        self,
        response_message: AgenteWhatsAppMessage,
        *,
        source_message: AgenteWhatsAppMessage | None = None,
    ) -> AgenteWhatsAppProcessingJob | None:
        if not self._settings.WHATSAPP_AUDIO_TTS_WORKER_ENABLED:
            return None
        if not self._should_generate_tts(response_message, source_message=source_message):
            return None

        idempotency_key = f"tts_generation:{response_message.id}"
        existing = (
            self._db.query(AgenteWhatsAppProcessingJob)
            .filter(AgenteWhatsAppProcessingJob.idempotency_key == idempotency_key)
            .first()
        )
        if existing:
            return existing

        now = _now_utc()
        job = AgenteWhatsAppProcessingJob(
            id=str(uuid.uuid4()),
            message_id=response_message.id,
            session_id=response_message.session_id,
            customer_id=response_message.customer_id,
            job_type="tts_generation",
            status="pending",
            attempts=0,
            max_attempts=3,
            idempotency_key=idempotency_key,
            payload_json=_json_dump(
                {
                    "response_message_id": response_message.id,
                    "source_message_id": source_message.id if source_message else None,
                    "audio_response_mode": self._settings_audio_response_mode(),
                }
            ),
            next_attempt_at=now,
            created_at=now,
            updated_at=now,
        )
        self._db.add(job)
        self._db.flush()
        return job

    def enqueue_pending_inbound(self, *, limit: int = 100) -> dict[str, int]:
        rows = (
            self._db.query(AgenteWhatsAppMessage)
            .filter(
                AgenteWhatsAppMessage.direction == "inbound",
                AgenteWhatsAppMessage.processing_status.in_(["recorded", "failed"]),
            )
            .order_by(AgenteWhatsAppMessage.created_at.asc())
            .limit(limit)
            .all()
        )
        enqueued = 0
        skipped = 0
        for message in rows:
            job_type = "audio_transcription" if message.message_type == "audio" else "inbound_message"
            existing = (
                self._db.query(AgenteWhatsAppProcessingJob.id)
                .filter(AgenteWhatsAppProcessingJob.idempotency_key == f"{job_type}:{message.id}")
                .first()
            )
            job = self.enqueue_inbound_message(message)
            if job and not existing:
                enqueued += 1
            else:
                skipped += 1
        self._db.flush()
        return {"eligible": len(rows), "enqueued": enqueued, "skipped": skipped}

    def process_audio_transcriptions(self, *, limit: int = 10) -> dict[str, int]:
        if not self._settings.WHATSAPP_AUDIO_INPUT_ENABLED or not self._settings.WHATSAPP_AUDIO_TRANSCRIPTION_WORKER_ENABLED:
            return {"processed": 0, "done": 0, "failed": 0}

        now = _now_utc()
        jobs = (
            self._db.query(AgenteWhatsAppProcessingJob)
            .filter(
                AgenteWhatsAppProcessingJob.job_type == "audio_transcription",
                AgenteWhatsAppProcessingJob.status.in_(["pending", "failed"]),
                or_(
                    AgenteWhatsAppProcessingJob.next_attempt_at.is_(None),
                    AgenteWhatsAppProcessingJob.next_attempt_at <= now,
                ),
                AgenteWhatsAppProcessingJob.attempts < AgenteWhatsAppProcessingJob.max_attempts,
            )
            .order_by(AgenteWhatsAppProcessingJob.created_at.asc())
            .limit(limit)
            .all()
        )
        processed = 0
        done = 0
        failed = 0
        for job in jobs:
            processed += 1
            job.status = "processing"
            job.attempts += 1
            job.locked_at = now
            job.started_at = now
            job.updated_at = now
            self._db.flush()
            try:
                message = self._db.query(AgenteWhatsAppMessage).filter(AgenteWhatsAppMessage.id == job.message_id).first()
                if message:
                    allowed, reason = AgenteWhatsAppRolloutService(self._db).check_message(message, "audio_input")
                    if not allowed:
                        job.status = "done"
                        job.error = reason
                        message.processing_status = "skipped"
                        message.transcription_status = "none"
                        message.transcription_error = reason
                        continue
                result = AgenteWhatsAppAudioService(self._db).transcribe_message(job.message_id)
                status = result.get("transcription_status")
                if status in {"done", "low_confidence"}:
                    message = message or (
                        self._db.query(AgenteWhatsAppMessage)
                        .filter(AgenteWhatsAppMessage.id == job.message_id)
                        .first()
                    )
                    if message:
                        self.enqueue_agent_response(message)
                    job.status = "done"
                    job.error = None
                    job.finished_at = _now_utc()
                    done += 1
                else:
                    job.status = "dead" if job.attempts >= job.max_attempts else "failed"
                    job.error = result.get("transcription_error") or "Falha na transcricao."
                    failed += 1
            except Exception as exc:
                job.status = "dead" if job.attempts >= job.max_attempts else "failed"
                job.error = str(exc)[:500]
                failed += 1
            finally:
                job.locked_at = None
                job.updated_at = _now_utc()
                if job.status == "failed":
                    job.next_attempt_at = _now_utc()
                self._db.flush()
        return {"processed": processed, "done": done, "failed": failed}

    def process_agent_responses(self, *, limit: int = 10) -> dict[str, int]:
        now = _now_utc()
        jobs = (
            self._db.query(AgenteWhatsAppProcessingJob)
            .filter(
                AgenteWhatsAppProcessingJob.job_type == "agent_response",
                AgenteWhatsAppProcessingJob.status.in_(["pending", "failed"]),
                or_(
                    AgenteWhatsAppProcessingJob.next_attempt_at.is_(None),
                    AgenteWhatsAppProcessingJob.next_attempt_at <= now,
                ),
                AgenteWhatsAppProcessingJob.attempts < AgenteWhatsAppProcessingJob.max_attempts,
            )
            .order_by(AgenteWhatsAppProcessingJob.created_at.asc())
            .limit(limit)
            .all()
        )
        processed = 0
        responded = 0
        skipped = 0
        failed = 0
        for job in jobs:
            processed += 1
            job.status = "processing"
            job.attempts += 1
            job.locked_at = now
            job.started_at = now
            job.updated_at = now
            self._db.flush()
            try:
                message = self._db.query(AgenteWhatsAppMessage).filter(AgenteWhatsAppMessage.id == job.message_id).first()
                if not message:
                    job.status = "dead"
                    job.error = "Mensagem de origem nao encontrada."
                    failed += 1
                    continue
                skip_reason = self._auto_reply_skip_reason(message)
                if skip_reason:
                    job.status = "done"
                    job.error = skip_reason
                    message.processing_status = "skipped"
                    skipped += 1
                    continue
                if self._existing_response(message.id):
                    job.status = "done"
                    job.error = "Resposta ja existente para a mensagem."
                    message.processing_status = "done"
                    skipped += 1
                    continue
                if message.message_type == "audio" and message.transcription_status == "low_confidence":
                    confirmation = self._queue_low_confidence_confirmation(message)
                    job.status = "done"
                    job.error = None
                    message.processing_status = "done"
                    message.processed_at = _now_utc()
                    if confirmation.id == message.id:
                        skipped += 1
                    else:
                        responded += 1
                    continue

                text_value = self._message_text(message)
                if not text_value:
                    job.status = "dead" if job.attempts >= job.max_attempts else "failed"
                    job.error = "Mensagem sem texto operacional para resposta."
                    failed += 1
                    continue

                from backend.services.agente_whatsapp_ai_service import AgenteWhatsAppAIService

                result = AgenteWhatsAppAIService(self._db).respond(
                    session_id=message.session_id,
                    message=text_value,
                    auto_queue=True,
                    record_inbound=False,
                    source_message_id=message.id,
                )
                response_payload = result.get("message") if isinstance(result.get("message"), dict) else None
                response_message_id = response_payload.get("id") if response_payload else None
                if response_message_id:
                    response_message = (
                        self._db.query(AgenteWhatsAppMessage)
                        .filter(AgenteWhatsAppMessage.id == response_message_id)
                        .first()
                    )
                    if response_message:
                        self.enqueue_tts_generation(response_message, source_message=message)
                job.status = "done"
                job.error = None
                message.processing_status = "done"
                message.processed_at = _now_utc()
                if result.get("message"):
                    responded += 1
                else:
                    skipped += 1
            except Exception as exc:
                job.status = "dead" if job.attempts >= job.max_attempts else "failed"
                job.error = str(exc)[:500]
                failed += 1
            finally:
                job.locked_at = None
                job.updated_at = _now_utc()
                if job.status == "failed":
                    job.next_attempt_at = _now_utc()
                self._db.flush()
        return {"processed": processed, "responded": responded, "skipped": skipped, "failed": failed}

    def process_tts_generations(self, *, limit: int = 10) -> dict[str, int]:
        if not self._settings.WHATSAPP_AUDIO_TTS_WORKER_ENABLED:
            return {"processed": 0, "generated": 0, "skipped": 0, "failed": 0}

        now = _now_utc()
        jobs = (
            self._db.query(AgenteWhatsAppProcessingJob)
            .filter(
                AgenteWhatsAppProcessingJob.job_type == "tts_generation",
                AgenteWhatsAppProcessingJob.status.in_(["pending", "failed"]),
                or_(
                    AgenteWhatsAppProcessingJob.next_attempt_at.is_(None),
                    AgenteWhatsAppProcessingJob.next_attempt_at <= now,
                ),
                AgenteWhatsAppProcessingJob.attempts < AgenteWhatsAppProcessingJob.max_attempts,
            )
            .order_by(AgenteWhatsAppProcessingJob.created_at.asc())
            .limit(limit)
            .all()
        )
        processed = 0
        generated = 0
        skipped = 0
        failed = 0
        for job in jobs:
            processed += 1
            job.status = "processing"
            job.attempts += 1
            job.locked_at = now
            job.started_at = now
            job.updated_at = now
            self._db.flush()
            try:
                message = self._db.query(AgenteWhatsAppMessage).filter(AgenteWhatsAppMessage.id == job.message_id).first()
                if not message:
                    job.status = "dead"
                    job.error = "Mensagem textual de origem nao encontrada."
                    failed += 1
                    continue
                if not self._should_generate_tts(message, source_message=self._source_message_from_job(job)):
                    job.status = "done"
                    job.error = "TTS ignorado por configuracao ou mensagem inelegivel."
                    skipped += 1
                    continue
                payload = _json_load(job.payload_json)
                result = AgenteWhatsAppAudioService(self._db).synthesize_response_audio(
                    message.id,
                    source_message_id=payload.get("source_message_id"),
                )
                if result.get("status") in {"generated", "existing"}:
                    AgenteWhatsAppOutboxService(self._db).enqueue_queued_messages(limit=20)
                    job.status = "done"
                    job.error = None
                    generated += 1
                else:
                    job.status = "dead" if job.attempts >= job.max_attempts else "failed"
                    job.error = "TTS nao gerou audio."
                    failed += 1
            except Exception as exc:
                job.status = "dead" if job.attempts >= job.max_attempts else "failed"
                job.error = str(exc)[:500]
                failed += 1
            finally:
                job.locked_at = None
                job.updated_at = _now_utc()
                if job.status == "failed":
                    job.next_attempt_at = _now_utc()
                self._db.flush()
        return {"processed": processed, "generated": generated, "skipped": skipped, "failed": failed}

    def _message_text(self, message: AgenteWhatsAppMessage) -> str:
        if message.message_type == "audio":
            return (message.transcription_text or message.body or "").strip()
        return (message.body or "").strip()

    def _existing_response(self, message_id: str) -> AgenteWhatsAppMessage | None:
        return (
            self._db.query(AgenteWhatsAppMessage)
            .filter(
                AgenteWhatsAppMessage.direction == "outbound",
                AgenteWhatsAppMessage.response_to_message_id == message_id,
            )
            .first()
        )

    def _auto_reply_skip_reason(self, message: AgenteWhatsAppMessage) -> str | None:
        if not self._settings.WHATSAPP_AI_AUTO_REPLY_ENABLED:
            return "Resposta automatica do Agente desativada por configuracao."
        session = message.session
        if not session:
            return "Sessao da mensagem nao encontrada."
        if not session.ai_enabled:
            return "IA desativada nesta sessao."
        if session.automation_blocked:
            return "Automacao bloqueada nesta sessao."
        if session.status in {"human", "ai_paused", "closed"}:
            return f"Sessao em status {session.status}; resposta automatica ignorada."
        if message.message_type == "audio" and message.transcription_status not in {"done", "low_confidence"}:
            return "Audio ainda sem transcricao pronta."
        if message.message_type == "audio" and not self._settings.WHATSAPP_AUDIO_TEXT_FALLBACK_ENABLED:
            return "Fallback textual de audio desativado por configuracao."
        allowed, reason = AgenteWhatsAppRolloutService(self._db).check_message(message, "ai_auto_reply")
        if not allowed:
            return reason
        return None

    def _settings_audio_response_mode(self) -> str:
        return str(AgenteWhatsAppAudioSettingsService(self._db).get_settings()["response_mode"]).strip().lower()

    def _should_generate_tts(
        self,
        response_message: AgenteWhatsAppMessage,
        *,
        source_message: AgenteWhatsAppMessage | None,
    ) -> bool:
        audio_settings = AgenteWhatsAppAudioSettingsService(self._db).get_settings()
        if not audio_settings["enabled"]:
            return False
        mode = str(audio_settings["response_mode"]).strip().lower()
        if mode in {"", "never", "manual_only"}:
            return False
        if response_message.direction != "outbound" or response_message.sender_type != "ai":
            return False
        if response_message.message_type != "text":
            return False
        if response_message.provider_status not in {"queued", "sent"}:
            return False
        if self._existing_tts_response(response_message.id):
            return False
        rollout_message = source_message or response_message
        allowed, _reason = AgenteWhatsAppRolloutService(self._db).check_message(rollout_message, "audio_output")
        if not allowed:
            return False
        if mode == "mirror_customer_audio":
            return bool(source_message and source_message.message_type == "audio")
        return mode == "always"

    def _existing_tts_response(self, response_message_id: str) -> AgenteWhatsAppMessage | None:
        return (
            self._db.query(AgenteWhatsAppMessage)
            .filter(
                AgenteWhatsAppMessage.direction == "outbound",
                AgenteWhatsAppMessage.message_type == "audio",
                AgenteWhatsAppMessage.response_to_message_id == response_message_id,
            )
            .first()
        )

    def _source_message_from_job(self, job: AgenteWhatsAppProcessingJob) -> AgenteWhatsAppMessage | None:
        payload = _json_load(job.payload_json)
        source_message_id = payload.get("source_message_id")
        if not source_message_id:
            return None
        return (
            self._db.query(AgenteWhatsAppMessage)
            .filter(AgenteWhatsAppMessage.id == source_message_id)
            .first()
        )

    def _queue_low_confidence_confirmation(self, message: AgenteWhatsAppMessage) -> AgenteWhatsAppMessage:
        if not self._settings.WHATSAPP_AUDIO_LOW_CONFIDENCE_HANDOFF_ENABLED:
            message.processing_status = "skipped"
            message.processed_at = _now_utc()
            self._db.flush()
            return message

        existing_response = self._existing_response(message.id)
        if existing_response:
            return existing_response
        body = (
            "Recebi seu audio, mas nao consegui entender com seguranca. "
            "Pode confirmar em texto o que voce deseja?"
        )
        from backend.services.agente_whatsapp_service import AgenteWhatsAppService

        response = AgenteWhatsAppService(self._db).add_message(
            message.session,
            direction="outbound",
            sender_type="ai",
            message_type="text",
            body=body,
            response_to_message_id=message.id,
            provider_status="queued",
            raw_payload={
                "source": "agente_whatsapp_agent_response",
                "reason": "low_confidence_transcription",
                "manager_review": {
                    "reviewer": "internal_manager_rules_v1",
                    "decision": "approve",
                    "risk_level": "low",
                    "approved_for_auto_queue": True,
                    "requires_human_review": False,
                    "reasons": [],
                    "warnings": ["Transcricao de baixa confianca; solicitada confirmacao do cliente."],
                },
            },
        )
        AgenteWhatsAppOutboxService(self._db).enqueue_queued_messages(limit=20)
        return response

    def list_jobs(self, *, status: str | None = None, limit: int = 100) -> list[AgenteWhatsAppProcessingJob]:
        q = self._db.query(AgenteWhatsAppProcessingJob)
        if status:
            q = q.filter(AgenteWhatsAppProcessingJob.status == status)
        return q.order_by(AgenteWhatsAppProcessingJob.created_at.desc()).limit(limit).all()

    def summary(self) -> dict[str, int]:
        rows = (
            self._db.query(AgenteWhatsAppProcessingJob.status, func.count(AgenteWhatsAppProcessingJob.id))
            .group_by(AgenteWhatsAppProcessingJob.status)
            .all()
        )
        counts = {"pending": 0, "processing": 0, "done": 0, "failed": 0, "dead": 0}
        for status, total in rows:
            counts[status or "pending"] = int(total or 0)
        counts["queued_messages"] = (
            self._db.query(func.count(AgenteWhatsAppMessage.id))
            .filter(
                AgenteWhatsAppMessage.direction == "inbound",
                AgenteWhatsAppMessage.processing_status == "queued",
            )
            .scalar()
            or 0
        )
        return counts

    def serialize_job(self, job: AgenteWhatsAppProcessingJob) -> dict[str, Any]:
        return {
            "id": job.id,
            "message_id": job.message_id,
            "session_id": job.session_id,
            "customer_id": job.customer_id,
            "job_type": job.job_type,
            "status": job.status,
            "attempts": job.attempts,
            "max_attempts": job.max_attempts,
            "idempotency_key": job.idempotency_key,
            "payload": _json_load(job.payload_json),
            "error": job.error,
            "next_attempt_at": job.next_attempt_at,
            "locked_at": job.locked_at,
            "started_at": job.started_at,
            "finished_at": job.finished_at,
            "created_at": job.created_at,
            "updated_at": job.updated_at,
        }
