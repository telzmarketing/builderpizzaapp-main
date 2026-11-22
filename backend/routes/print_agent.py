from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.core.response import err, ok
from backend.database import get_db
from backend.schemas.print_center import PrintAgentHeartbeatIn, PrintAgentJobStatusIn, PrintAgentPairIn
from backend.services.print_agent_service import PrintAgentService

router = APIRouter(prefix="/print-agent/v1", tags=["print-agent"])


def _run(fn):
    try:
        return fn()
    except DomainError as exc:
        return err(exc)


def _service(db: Session, tenant_id: str = "") -> PrintAgentService:
    return PrintAgentService(db, tenant_id)


def _credential(db: Session, authorization: str | None, request: Request):
    if not authorization or not authorization.startswith("Bearer "):
        from backend.services.print_agent_service import PrintAgentUnauthorized
        raise PrintAgentUnauthorized("Token do agente não fornecido.")
    return _service(db).authenticate(authorization.removeprefix("Bearer ").strip(), request.client.host if request.client else None)


@router.post("/pair")
def pair(body: PrintAgentPairIn, request: Request, db: Session = Depends(get_db)):
    return _run(lambda: _pair(body, request, db))


def _pair(body, request: Request, db: Session):
    station, token = _service(db).pair(body, request.client.host if request.client else None)
    return ok({"access_token": token, "token_type": "Bearer", "tenant_id": station.tenant_id, "station_id": station.id, "station_code": station.code})


@router.get("/jobs/next")
def next_job(request: Request, authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    return _run(lambda: _next_job(request, authorization, db))


def _next_job(request, authorization, db):
    credential = _credential(db, authorization, request)
    service = _service(db, credential.tenant_id)
    return ok({"job": service.next_job(credential)})


@router.post("/jobs/{job_id}/status")
def update_status(job_id: str, body: PrintAgentJobStatusIn, request: Request, authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    return _run(lambda: _update_status(job_id, body, request, authorization, db))


def _update_status(job_id, body, request, authorization, db):
    credential = _credential(db, authorization, request)
    service = _service(db, credential.tenant_id)
    return ok(service.update_job_status(credential, job_id, body))


@router.post("/heartbeat")
def heartbeat(body: PrintAgentHeartbeatIn, request: Request, authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    return _run(lambda: _heartbeat(body, request, authorization, db))


def _heartbeat(body, request, authorization, db):
    credential = _credential(db, authorization, request)
    return ok(_service(db, credential.tenant_id).heartbeat(credential, body))
