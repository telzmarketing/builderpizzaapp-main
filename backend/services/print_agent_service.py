from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.core.exceptions import DomainError
from backend.models.print_center import PrintAgentCredential, PrintAgentPairing, PrintJob, PrintJobEvent, PrintPrinter, PrintStation


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class PrintAgentNotFound(DomainError):
    http_status = 404


class PrintAgentUnauthorized(DomainError):
    http_status = 401


class PrintAgentConflict(DomainError):
    http_status = 409


class PrintAgentService:
    def __init__(self, db: Session, tenant_id: str, actor_id: str | None = None):
        self.db = db
        self.tenant_id = tenant_id
        self.actor_id = actor_id

    def create_pairing_code(self, station_id: str, ttl_minutes: int) -> str:
        station = self.db.query(PrintStation).filter_by(id=station_id, tenant_id=self.tenant_id).first()
        if not station:
            raise PrintAgentNotFound("Estação de impressão não encontrada.")
        now = _now()
        self.db.query(PrintAgentPairing).filter(
            PrintAgentPairing.tenant_id == self.tenant_id,
            PrintAgentPairing.station_id == station_id,
            PrintAgentPairing.used_at.is_(None),
            PrintAgentPairing.expires_at > now,
        ).update({PrintAgentPairing.used_at: now}, synchronize_session=False)
        code = secrets.token_urlsafe(32)
        self.db.add(PrintAgentPairing(
            id=str(uuid.uuid4()), tenant_id=self.tenant_id, station_id=station_id,
            code_hash=_hash(code), expires_at=now + timedelta(minutes=ttl_minutes),
            created_by_admin_id=self.actor_id,
        ))
        self.db.commit()
        return code

    def pair(self, body, ip_address: str | None = None) -> tuple[PrintStation, str]:
        pairing = self.db.query(PrintAgentPairing).filter_by(
            code_hash=_hash(body.code),
        ).with_for_update().first()
        now = _now()
        if not pairing or pairing.expires_at <= now or pairing.used_at is not None:
            raise PrintAgentUnauthorized("Código de pareamento inválido ou expirado.")
        station = self.db.query(PrintStation).filter_by(id=pairing.station_id, tenant_id=pairing.tenant_id, active=True).first()
        if not station:
            raise PrintAgentUnauthorized("Estação de impressão indisponível.")
        token = secrets.token_urlsafe(48)
        credential = self.db.query(PrintAgentCredential).filter_by(
            tenant_id=pairing.tenant_id, station_id=station.id,
        ).first()
        if credential is None:
            credential = PrintAgentCredential(id=str(uuid.uuid4()), tenant_id=pairing.tenant_id, station_id=station.id)
            self.db.add(credential)
        credential.token_hash = _hash(token)
        credential.agent_version = body.agent_version
        credential.hostname = body.hostname
        credential.last_ip = ip_address
        credential.last_seen_at = now
        credential.revoked_at = None
        pairing.used_at = now
        station.hostname = body.hostname
        station.connected = True
        station.last_seen_at = now
        self.db.commit()
        return station, token

    def authenticate(self, token: str, ip_address: str | None = None) -> PrintAgentCredential:
        credential = self.db.query(PrintAgentCredential).filter_by(token_hash=_hash(token), revoked_at=None).first()
        if not credential:
            raise PrintAgentUnauthorized("Token do agente inválido ou revogado.")
        credential.last_ip = ip_address
        credential.last_seen_at = _now()
        self.db.commit()
        return credential

    def heartbeat(self, credential: PrintAgentCredential, body) -> dict:
        now = _now()
        station = self._station(credential.station_id)
        credential.agent_version = body.agent_version or credential.agent_version
        credential.hostname = body.hostname or credential.hostname
        credential.last_seen_at = now
        station.connected = True
        station.last_seen_at = now
        if body.hostname:
            station.hostname = body.hostname
        for item in body.printers:
            code = str(item.get("code", "")).strip()
            if not code:
                continue
            printer = self.db.query(PrintPrinter).filter_by(
                tenant_id=self.tenant_id, station_id=station.id, code=code,
            ).first()
            if printer:
                if item.get("status") is not None:
                    printer.status = str(item["status"])[:20]
                printer.last_seen_at = now
        self.db.commit()
        return {"station_id": station.id, "connected": True, "last_seen_at": now}

    def next_job(self, credential: PrintAgentCredential) -> dict | None:
        station = self._station(credential.station_id)
        query = self.db.query(PrintJob).filter(
            PrintJob.tenant_id == self.tenant_id,
            PrintJob.station_id == station.id,
            PrintJob.status.in_(["pending", "received", "queued"]),
        ).order_by(PrintJob.priority.desc(), PrintJob.created_at.asc()).with_for_update(skip_locked=True)
        job = query.first()
        if not job:
            return None
        previous = job.status
        job.status = "processing"
        job.attempts += 1
        self.db.add(PrintJobEvent(
            id=str(uuid.uuid4()), tenant_id=self.tenant_id, job_id=job.id,
            from_status=previous, to_status="processing", message="Trabalho reservado pelo agente Windows.",
        ))
        self.db.commit()
        self.db.refresh(job)
        return self.serialize_job(job)

    def update_job_status(self, credential: PrintAgentCredential, job_id: str, body) -> dict:
        job = self.db.query(PrintJob).filter_by(id=job_id, tenant_id=self.tenant_id, station_id=credential.station_id).first()
        if not job:
            raise PrintAgentNotFound("Trabalho de impressão não encontrado.")
        if job.status == body.status:
            return self.serialize_job(job)
        allowed = {
            "processing": {"spooler_submitted", "printed", "error", "uncertain", "cancelled"},
            "spooler_submitted": {"printed", "error", "uncertain"},
        }
        if body.status not in allowed.get(job.status, set()):
            raise PrintAgentConflict(f"Transição de impressão inválida: {job.status} → {body.status}.")
        previous = job.status
        job.status = body.status
        job.last_error = body.message if body.status in {"error", "uncertain"} else None
        self.db.add(PrintJobEvent(
            id=str(uuid.uuid4()), tenant_id=self.tenant_id, job_id=job.id,
            from_status=previous, to_status=body.status, message=body.message,
        ))
        self.db.commit()
        self.db.refresh(job)
        return self.serialize_job(job)

    def _station(self, station_id: str) -> PrintStation:
        station = self.db.query(PrintStation).filter_by(id=station_id, tenant_id=self.tenant_id).first()
        if not station:
            raise PrintAgentUnauthorized("Estação do agente não pertence ao tenant.")
        return station

    def serialize_job(self, job: PrintJob) -> dict:
        payload = {key: value for key, value in job.__dict__.items() if not key.startswith("_")}
        printer = self.db.query(PrintPrinter).filter_by(id=job.printer_id, tenant_id=job.tenant_id).first()
        payload["printer_name"] = printer.name if printer else None
        return payload


class PrintAgentReleaseService:
    @staticmethod
    def metadata() -> dict:
        settings = get_settings()
        path = Path(settings.PRINT_AGENT_ARTIFACT_PATH).expanduser() if settings.PRINT_AGENT_ARTIFACT_PATH else None
        available = bool(path and path.is_file())
        sha256 = None
        size_bytes = None
        if available:
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            sha256 = digest.hexdigest()
            size_bytes = path.stat().st_size
        version = settings.PRINT_AGENT_VERSION or None
        return {
            "available": available,
            "version": version,
            "file_name": settings.PRINT_AGENT_FILE_NAME,
            "download_url": "/api/admin/print-center/agent-release/download" if available else None,
            "sha256": sha256,
            "size_bytes": size_bytes,
            "min_windows_version": settings.PRINT_AGENT_MIN_WINDOWS_VERSION,
            "notes": settings.PRINT_AGENT_RELEASE_NOTES or None,
        }

    @staticmethod
    def artifact_path() -> Path | None:
        raw = get_settings().PRINT_AGENT_ARTIFACT_PATH
        path = Path(raw).expanduser() if raw else None
        return path if path and path.is_file() else None
