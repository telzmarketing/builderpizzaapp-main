from __future__ import annotations

import uuid
from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.models.print_center import PrintJob, PrintJobEvent, PrintPrinter, PrintRoutingRule, PrintStation


class PrintCenterNotFound(DomainError):
    http_status = 404


class PrintCenterConflict(DomainError):
    http_status = 409


class PrintCenterService:
    def __init__(self, db: Session, tenant_id: str, actor_id: str):
        self.db, self.tenant_id, self.actor_id = db, tenant_id, actor_id

    def _station(self, station_id: str) -> PrintStation:
        row = self.db.query(PrintStation).filter_by(id=station_id, tenant_id=self.tenant_id).first()
        if not row: raise PrintCenterNotFound("Estação de impressão não encontrada.")
        return row

    def _printer(self, printer_id: str) -> PrintPrinter:
        row = self.db.query(PrintPrinter).filter_by(id=printer_id, tenant_id=self.tenant_id).first()
        if not row: raise PrintCenterNotFound("Impressora não encontrada.")
        return row

    def create_station(self, body):
        if self.db.query(PrintStation).filter_by(tenant_id=self.tenant_id, code=body.code).first():
            raise PrintCenterConflict("Já existe uma estação com este código.")
        row = PrintStation(id=str(uuid.uuid4()), tenant_id=self.tenant_id, **body.model_dump())
        self.db.add(row); self.db.commit(); self.db.refresh(row); return row

    def create_printer(self, body):
        station = self._station(body.station_id)
        if self.db.query(PrintPrinter).filter_by(tenant_id=self.tenant_id, station_id=station.id, code=body.code).first():
            raise PrintCenterConflict("Já existe uma impressora com este código nesta estação.")
        row = PrintPrinter(id=str(uuid.uuid4()), tenant_id=self.tenant_id, **body.model_dump())
        self.db.add(row); self.db.commit(); self.db.refresh(row); return row

    def create_rule(self, body):
        self._printer(body.printer_id)
        row = PrintRoutingRule(id=str(uuid.uuid4()), tenant_id=self.tenant_id, created_by_admin_id=self.actor_id, **body.model_dump())
        self.db.add(row); self.db.commit(); self.db.refresh(row); return row

    def create_job(self, body, idempotency_key: str):
        existing = self.db.query(PrintJob).filter_by(tenant_id=self.tenant_id, idempotency_key=idempotency_key).first()
        if existing:
            comparable = body.model_dump()
            if any(getattr(existing, key) != value for key, value in comparable.items()):
                raise PrintCenterConflict("A chave de idempotência já foi usada para outro trabalho.")
            return existing
        printer = self._printer(body.printer_id)
        if body.station_id and body.station_id != printer.station_id:
            raise PrintCenterConflict("A estação informada não corresponde à impressora.")
        values = body.model_dump()
        values["station_id"] = body.station_id or printer.station_id
        row = PrintJob(id=str(uuid.uuid4()), tenant_id=self.tenant_id,
                       idempotency_key=idempotency_key, created_by_admin_id=self.actor_id, status="queued", **values)
        self.db.add(row); self.db.flush()
        self._event(row, None, "queued", "Trabalho criado na fila.")
        self.db.commit(); self.db.refresh(row); return row

    def update_status(self, job_id: str, body):
        row = self._job(job_id)
        allowed = {"queued": {"processing", "cancelled", "error"}, "processing": {"spooler_submitted", "error", "uncertain", "cancelled"},
                   "spooler_submitted": {"printed", "error", "uncertain"}, "received": {"queued", "error"}, "pending": {"received", "queued"},
                   "error": {"queued", "cancelled"}, "uncertain": {"queued", "cancelled"}, "printed": set(), "cancelled": set()}
        if body.status not in allowed.get(row.status, set()):
            raise PrintCenterConflict(f"Transição de impressão inválida: {row.status} → {body.status}.")
        previous = row.status; row.status = body.status; row.last_error = body.message if body.status in {"error", "uncertain"} else None
        if body.status == "processing": row.attempts += 1
        self._event(row, previous, body.status, body.message); self.db.commit(); self.db.refresh(row); return row

    def retry(self, job_id: str):
        row = self._job(job_id)
        if row.status not in {"error", "uncertain"}: raise PrintCenterConflict("Somente trabalhos com erro ou estado incerto podem ser reenfileirados.")
        previous = row.status; row.status = "queued"; row.last_error = None; self._event(row, previous, "queued", "Reimpressão manual solicitada.")
        self.db.commit(); self.db.refresh(row); return row

    def cancel(self, job_id: str):
        row = self._job(job_id)
        if row.status in {"printed", "cancelled"}: raise PrintCenterConflict("O trabalho não pode mais ser cancelado.")
        previous = row.status; row.status = "cancelled"; self._event(row, previous, "cancelled", "Cancelado pelo operador.")
        self.db.commit(); self.db.refresh(row); return row

    def _job(self, job_id):
        row = self.db.query(PrintJob).filter_by(id=job_id, tenant_id=self.tenant_id).first()
        if not row: raise PrintCenterNotFound("Trabalho de impressão não encontrado.")
        return row

    def _event(self, row, previous, status, message):
        self.db.add(PrintJobEvent(id=str(uuid.uuid4()), tenant_id=self.tenant_id, job_id=row.id, from_status=previous, to_status=status, message=message, actor_id=self.actor_id))

    def overview(self):
        jobs = self.db.query(PrintJob).filter_by(tenant_id=self.tenant_id)
        return {"stations": self.db.query(PrintStation).filter_by(tenant_id=self.tenant_id, active=True).count(),
                "printers": self.db.query(PrintPrinter).filter_by(tenant_id=self.tenant_id, active=True).count(),
                "pending_jobs": jobs.filter(PrintJob.status.in_(["pending", "received", "queued", "processing", "uncertain"])).count(),
                "processed_jobs": jobs.filter(PrintJob.status == "printed").count(),
                "failed_jobs": jobs.filter(PrintJob.status == "error").count()}
