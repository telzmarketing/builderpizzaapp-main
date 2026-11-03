from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.core.rbac_authorization import AuthorizedTenantActor, require_rbac_permission
from backend.core.response import err, ok
from backend.database import get_db
from backend.schemas.production_vision import CameraIn, CaptureConfigIn, CaptureEventIn, EvidenceHoldIn, FinishIn, IncidentIn, OccupyZoneIn, PhotoIn, SessionIn, SettingsIn, StationIn, ZoneIn
from backend.services.production_vision_service import ProductionVisionService

router = APIRouter(prefix="/production-vision", tags=["production-vision"])
read = Depends(require_rbac_permission("cozinha", "view"))
write = Depends(require_rbac_permission("cozinha", "edit"))


def svc(db: Session, actor: AuthorizedTenantActor) -> ProductionVisionService:
    return ProductionVisionService(db, actor.tenant_id)


def call(fn):
    try:
        return ok(fn())
    except DomainError as exc:
        return err(exc)


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), actor: AuthorizedTenantActor = read): return ok(svc(db, actor).dashboard())

@router.get("/cameras")
def cameras(db: Session = Depends(get_db), actor: AuthorizedTenantActor = read): return ok(svc(db, actor).cameras())

@router.get("/stations")
def stations(db: Session = Depends(get_db), actor: AuthorizedTenantActor = read): return ok(svc(db, actor).stations())

@router.post("/stations", status_code=201)
def create_station(body: StationIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = write): return call(lambda: svc(db, actor).save_station(body))

@router.put("/stations/{station_id}")
def update_station(station_id: str, body: StationIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = write): return call(lambda: svc(db, actor).save_station(body, station_id))

@router.delete("/stations/{station_id}")
def delete_station(station_id: str, db: Session = Depends(get_db), actor: AuthorizedTenantActor = write): return call(lambda: svc(db, actor).delete_station(station_id))

@router.get("/capture-config")
def capture_config(station_id: str = Query(..., min_length=1, max_length=80), db: Session = Depends(get_db), actor: AuthorizedTenantActor = read): return call(lambda: svc(db, actor).capture_config(station_id))

@router.put("/capture-config")
def update_capture_config(body: CaptureConfigIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = write): return call(lambda: svc(db, actor).update_capture_config(body))

@router.get("/zones")
def zones(db: Session = Depends(get_db), actor: AuthorizedTenantActor = read): return ok(svc(db, actor).zones())

@router.post("/zones", status_code=201)
def create_zone(body: ZoneIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = write): return call(lambda: svc(db, actor).save_zone(body))

@router.put("/zones/{zone_id}")
def update_zone(zone_id: str, body: ZoneIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = write): return call(lambda: svc(db, actor).save_zone(body, zone_id))

@router.delete("/zones/{zone_id}")
def delete_zone(zone_id: str, db: Session = Depends(get_db), actor: AuthorizedTenantActor = write): return call(lambda: svc(db, actor).delete_zone(zone_id))

@router.post("/zones/{zone_id}/occupy", status_code=201)
def occupy_zone(zone_id: str, body: OccupyZoneIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = write): return call(lambda: svc(db, actor).occupy_zone(zone_id, body))

@router.post("/zones/{zone_id}/release")
def release_zone(zone_id: str, session_id: str = Query(...), db: Session = Depends(get_db), actor: AuthorizedTenantActor = write): return ok(svc(db, actor).release_zone(zone_id, session_id))

@router.get("/settings")
def get_settings(db: Session = Depends(get_db), actor: AuthorizedTenantActor = read): return ok(svc(db, actor).settings())

@router.put("/settings")
def update_settings(body: SettingsIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = write): return ok(svc(db, actor).update_settings(body))

@router.get("/diagnostics")
def diagnostics(db: Session = Depends(get_db), actor: AuthorizedTenantActor = read): return ok(svc(db, actor).diagnostics())

@router.get("/retention/dry-run")
def retention_dry_run(db: Session = Depends(get_db), actor: AuthorizedTenantActor = read): return ok(svc(db, actor).retention_dry_run())

@router.post("/retention/evaluate")
def retention_evaluate(db: Session = Depends(get_db), actor: AuthorizedTenantActor = write): return ok(svc(db, actor).retention_dry_run())

@router.post("/cameras", status_code=201)
def create_camera(body: CameraIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = write): return call(lambda: svc(db, actor).save_camera(body))

@router.put("/cameras/{camera_id}")
def update_camera(camera_id: str, body: CameraIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = write): return call(lambda: svc(db, actor).save_camera(body, camera_id))

@router.post("/sessions", status_code=201)
def create_session(body: SessionIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = write): return call(lambda: svc(db, actor).create_session(body, actor.user_id))

@router.post("/sessions/{session_id}/photos", status_code=201)
def add_photo(session_id: str, body: PhotoIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = write): return call(lambda: svc(db, actor).add_photo(session_id, body))

@router.post("/sessions/{session_id}/captures", status_code=201)
def capture_event(session_id: str, body: CaptureEventIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = write): return call(lambda: svc(db, actor).capture_event(session_id, body, actor.user_id))

@router.get("/sessions/{session_id}/capture-state")
def capture_state(session_id: str, db: Session = Depends(get_db), actor: AuthorizedTenantActor = read): return call(lambda: svc(db, actor).capture_state(session_id))

@router.post("/sessions/{session_id}/finish")
def finish_session(session_id: str, body: FinishIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = write): return call(lambda: svc(db, actor).finish(session_id, body))

@router.get("/history")
def history(session_id: str | None = Query(default=None), photo_id: str | None = Query(default=None), db: Session = Depends(get_db), actor: AuthorizedTenantActor = read): return ok(svc(db, actor).history(session_id=session_id, photo_id=photo_id))

@router.get("/sessions/{session_id}/history")
def session_history(session_id: str, db: Session = Depends(get_db), actor: AuthorizedTenantActor = read): return ok(svc(db, actor).history(session_id=session_id))

@router.get("/photos/{photo_id}/history")
def photo_history(photo_id: str, db: Session = Depends(get_db), actor: AuthorizedTenantActor = read): return ok(svc(db, actor).history(photo_id=photo_id))

@router.get("/incidents")
def incidents(db: Session = Depends(get_db), actor: AuthorizedTenantActor = read): return ok(svc(db, actor).incidents())

@router.post("/incidents", status_code=201)
def create_incident(body: IncidentIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = write): return call(lambda: svc(db, actor).add_incident(body))

@router.get("/evidence-holds")
def evidence_holds(db: Session = Depends(get_db), actor: AuthorizedTenantActor = read): return ok(svc(db, actor).holds())

@router.post("/evidence-holds", status_code=201)
def create_hold(body: EvidenceHoldIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = write): return call(lambda: svc(db, actor).add_hold(body, actor.user_id))

@router.delete("/evidence-holds/{hold_key}")
def release_hold(hold_key: str, db: Session = Depends(get_db), actor: AuthorizedTenantActor = write): return call(lambda: svc(db, actor).release_hold(hold_key))
