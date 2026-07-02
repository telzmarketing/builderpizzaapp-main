from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from backend.config import PROJECT_ROOT, get_settings
from backend.models.agente_whatsapp import AgenteWhatsAppAudioArtifact, AgenteWhatsAppMessage


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _same_or_before(value: datetime | None, limit: datetime) -> bool:
    if not value:
        return False
    if value.tzinfo is None and limit.tzinfo is not None:
        value = value.replace(tzinfo=timezone.utc)
    if value.tzinfo is not None and limit.tzinfo is None:
        limit = limit.replace(tzinfo=timezone.utc)
    return value <= limit


class AgenteWhatsAppRetentionService:
    def __init__(self, db: Session):
        self._db = db
        self._settings = get_settings()

    def audio_cleanup(self, *, dry_run: bool = True, limit: int | None = None) -> dict[str, Any]:
        days = max(1, int(self._settings.WHATSAPP_AUDIO_RETENTION_DAYS or 30))
        batch_size = max(1, min(int(limit or self._settings.WHATSAPP_AUDIO_RETENTION_BATCH_SIZE or 50), 500))
        cutoff = _now_utc() - timedelta(days=days)
        storage_root = (PROJECT_ROOT / self._settings.WHATSAPP_AUDIO_STORAGE_DIR).resolve()

        rows = (
            self._db.query(AgenteWhatsAppAudioArtifact)
            .filter(
                AgenteWhatsAppAudioArtifact.status.in_(["stored", "generated"]),
                AgenteWhatsAppAudioArtifact.created_at <= cutoff,
            )
            .order_by(AgenteWhatsAppAudioArtifact.created_at.asc())
            .limit(batch_size)
            .all()
        )

        scanned = len(rows)
        eligible = 0
        deleted_files = 0
        cleared_messages = 0
        skipped = 0
        errors: list[dict[str, str]] = []

        for artifact in rows:
            if not _same_or_before(artifact.created_at, cutoff):
                skipped += 1
                continue
            path = self._artifact_path(artifact.storage_key, storage_root=storage_root)
            if artifact.storage_key and path is None:
                skipped += 1
                errors.append({"artifact_id": artifact.id, "error": "storage_key fora do diretorio de audio"})
                continue

            eligible += 1
            if dry_run:
                continue

            try:
                if path and path.exists() and path.is_file():
                    path.unlink()
                    deleted_files += 1
                self._mark_deleted(artifact)
                cleared_messages += self._clear_message_media_if_needed(artifact.message)
            except OSError as exc:
                skipped += 1
                errors.append({"artifact_id": artifact.id, "error": str(exc)[:300]})

        if not dry_run:
            self._db.flush()

        return {
            "dry_run": dry_run,
            "enabled": bool(self._settings.WHATSAPP_AUDIO_RETENTION_CLEANUP_ENABLED),
            "retention_days": days,
            "cutoff_at": cutoff,
            "scanned": scanned,
            "eligible": eligible,
            "deleted_files": deleted_files,
            "cleared_messages": cleared_messages,
            "skipped": skipped,
            "errors": errors[:20],
        }

    def should_run_automatic_cleanup(self) -> bool:
        return bool(self._settings.WHATSAPP_AUDIO_RETENTION_CLEANUP_ENABLED)

    def _artifact_path(self, storage_key: str | None, *, storage_root: Path) -> Path | None:
        if not storage_key:
            return None
        path = (PROJECT_ROOT / storage_key.lstrip("/")).resolve()
        if path != storage_root and storage_root not in path.parents:
            return None
        return path

    def _mark_deleted(self, artifact: AgenteWhatsAppAudioArtifact) -> None:
        artifact.status = "deleted"
        artifact.storage_key = None
        artifact.media_url = None
        artifact.updated_at = _now_utc()

    def _clear_message_media_if_needed(self, message: AgenteWhatsAppMessage | None) -> int:
        if not message:
            return 0
        active = [
            artifact
            for artifact in message.audio_artifacts
            if artifact.status in {"stored", "generated"} and artifact.storage_key
        ]
        if active:
            return 0
        message.media_url = None
        message.media_storage_key = None
        message.media_size_bytes = None
        return 1
