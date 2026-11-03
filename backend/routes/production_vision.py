from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.core.rbac_authorization import AuthorizedTenantActor, require_rbac_permission
from backend.core.response import err, ok
from backend.database import get_db
from backend.core.exceptions import DomainError
from backend.schemas.production_vision import CameraIn, FinishIn, PhotoIn, SessionIn
from backend.services.production_vision_service import ProductionVisionService

router = APIRouter(prefix="/production-vision", tags=["production-vision"])


def service(db: Session, actor: AuthorizedTenantActor) -> ProductionVisionService:
    return ProductionVisionService(db, actor.tenant_id)


read = Depends(require_rbac_permission("cozinha", "view"))
write = Depends(require_rbac_permission("cozinha", "edit"))


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), actor: AuthorizedTenantActor = read):
    return ok(service(db, actor).dashboard())


@router.get("/cameras")
def cameras(db: Session = Depends(get_db), actor: AuthorizedTenantActor = read):
    return ok(service(db, actor).cameras())


@router.get("/stations")
def stations(db: Session = Depends(get_db), actor: AuthorizedTenantActor = read):
    return ok(service(db, actor).stations())


@router.post("/cameras", status_code=201)
def create_camera(body: CameraIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = write):
    try: return ok(service(db, actor).save_camera(body), status_code=201)
    except DomainError as exc: return err(exc)


@router.put("/cameras/{camera_id}")
def update_camera(camera_id: str, body: CameraIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = write):
    try: return ok(service(db, actor).save_camera(body, camera_id))
    except DomainError as exc: return err(exc)


@router.post("/sessions", status_code=201)
def create_session(body: SessionIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = write):
    try: return ok(service(db, actor).create_session(body, actor.user_id), status_code=201)
    except DomainError as exc: return err(exc)


@router.post("/sessions/{session_id}/photos", status_code=201)
def add_photo(session_id: str, body: PhotoIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = write):
    try: return ok(service(db, actor).add_photo(session_id, body), status_code=201)
    except DomainError as exc: return err(exc)


@router.post("/sessions/{session_id}/finish")
def finish_session(session_id: str, body: FinishIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = write):
    try: return ok(service(db, actor).finish(session_id, body))
    except DomainError as exc: return err(exc)
