from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.core.rbac_authorization import AuthorizedTenantActor, require_rbac_permission
from backend.core.response import created, err, err_msg, ok
from backend.database import get_db
from backend.models.print_center import PrintJob, PrintPrinter, PrintRoutingRule, PrintStation
from backend.schemas.print_center import PrintAgentPairingCodeIn, PrintJobIn, PrintStatusIn, PrinterIn, RoutingRuleIn, StationIn
from backend.services.print_center_service import PrintCenterService
from backend.services.print_agent_service import PrintAgentReleaseService
import json
import uuid
from backend.models.rbac import AdminAuditLog

router = APIRouter(prefix="/admin/print-center", tags=["print-center"])
read = Depends(require_rbac_permission("configuracoes", "view"))
write = Depends(require_rbac_permission("configuracoes", "edit"))


def svc(db, actor): return PrintCenterService(db, actor.tenant_id, actor.user_id)
def run(fn):
    try: return fn()
    except DomainError as exc: return err(exc)

def public(row):
    return {key: value for key, value in row.__dict__.items() if not key.startswith("_")}


@router.get("/overview")
def overview(db: Session = Depends(get_db), actor: AuthorizedTenantActor = read): return ok(svc(db, actor).overview())

@router.get("/stations")
def stations(db: Session = Depends(get_db), actor: AuthorizedTenantActor = read): return ok([public(x) for x in db.query(PrintStation).filter_by(tenant_id=actor.tenant_id).all()])

@router.post("/stations", status_code=201)
def create_station(body: StationIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = write): return run(lambda: created(svc(db, actor).create_station(body).__dict__))

@router.patch("/stations/{station_id}")
def update_station(station_id: str, body: dict, db: Session = Depends(get_db), actor: AuthorizedTenantActor = write):
    station = svc(db, actor)._station(station_id)
    if "active" in body: station.active = bool(body["active"])
    db.commit(); db.refresh(station)
    return ok({"id": station.id, "name": station.name, "active": station.active, "connected": station.connected, "hostname": station.hostname, "last_seen_at": station.last_seen_at})

@router.get("/printers")
def printers(db: Session = Depends(get_db), actor: AuthorizedTenantActor = read): return ok([public(x) for x in db.query(PrintPrinter).filter_by(tenant_id=actor.tenant_id).all()])

@router.post("/printers", status_code=201)
def create_printer(body: PrinterIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = write): return run(lambda: created(svc(db, actor).create_printer(body).__dict__))

@router.post("/printers/{printer_id}/test")
def test_printer(printer_id: str, db: Session = Depends(get_db), actor: AuthorizedTenantActor = write):
    printer = svc(db, actor)._printer(printer_id)
    return ok({"accepted": False, "printer_id": printer.id, "message": "A estação deve estar conectada para aceitar um trabalho de teste."})

@router.get("/rules")
def rules(db: Session = Depends(get_db), actor: AuthorizedTenantActor = read): return ok([public(x) for x in db.query(PrintRoutingRule).filter_by(tenant_id=actor.tenant_id).all()])

@router.post("/rules", status_code=201)
def create_rule(body: RoutingRuleIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = write): return run(lambda: created(svc(db, actor).create_rule(body).__dict__))

@router.get("/jobs")
def jobs(status: str | None = Query(default=None), db: Session = Depends(get_db), actor: AuthorizedTenantActor = read):
    query = db.query(PrintJob).filter_by(tenant_id=actor.tenant_id)
    if status: query = query.filter(PrintJob.status == status)
    return ok([public(x) for x in query.order_by(PrintJob.priority.desc(), PrintJob.created_at.asc()).limit(500).all()])

@router.post("/jobs", status_code=201)
def create_job(body: PrintJobIn, idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=1, max_length=200), db: Session = Depends(get_db), actor: AuthorizedTenantActor = write): return run(lambda: created(svc(db, actor).create_job(body, idempotency_key).__dict__))

@router.post("/jobs/{job_id}/status")
def update_status(job_id: str, body: PrintStatusIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = write): return run(lambda: ok(svc(db, actor).update_status(job_id, body).__dict__))

@router.post("/jobs/{job_id}/retry")
def retry(job_id: str, db: Session = Depends(get_db), actor: AuthorizedTenantActor = write): return run(lambda: ok(svc(db, actor).retry(job_id).__dict__))

@router.post("/jobs/{job_id}/cancel")
def cancel(job_id: str, db: Session = Depends(get_db), actor: AuthorizedTenantActor = write): return run(lambda: ok(svc(db, actor).cancel(job_id).__dict__))


@router.post("/stations/{station_id}/pairing-code")
def create_pairing_code(station_id: str, body: PrintAgentPairingCodeIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = write):
    from backend.services.print_agent_service import PrintAgentService
    code = PrintAgentService(db, actor.tenant_id, actor.user_id).create_pairing_code(station_id, body.ttl_minutes)
    db.add(AdminAuditLog(
        id=str(uuid.uuid4()), tenant_id=actor.tenant_id, user_id=actor.user_id, user_name=actor.user_name,
        action="create_pairing_code", module_key="configuracoes", entity_type="print_station", entity_id=station_id,
        new_value=json.dumps({"ttl_minutes": body.ttl_minutes}),
    ))
    db.commit()
    return created({"station_id": station_id, "code": code, "expires_in_minutes": body.ttl_minutes}, "Código de pareamento criado.")


@router.get("/agent-release")
def agent_release(db: Session = Depends(get_db), actor: AuthorizedTenantActor = read):
    return ok(PrintAgentReleaseService.metadata())


@router.get("/agent-release/download")
def download_agent_release(db: Session = Depends(get_db), actor: AuthorizedTenantActor = read):
    path = PrintAgentReleaseService.artifact_path()
    if path is None:
        return err_msg("Instalador do agente ainda não está disponível.", code="PrintAgentArtifactUnavailable", status_code=404)
    settings = __import__("backend.config", fromlist=["get_settings"]).get_settings()
    return FileResponse(path, filename=settings.PRINT_AGENT_FILE_NAME, media_type="application/vnd.microsoft.portable-executable")
