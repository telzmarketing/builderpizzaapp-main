from fastapi import APIRouter, Depends, File, Form, Header, UploadFile
from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.core.response import created, err, ok
from backend.core.rbac_authorization import AuthorizedTenantActor, require_rbac_permission
from backend.database import get_db
from backend.models.print_order import PrintOrderCatalogMapping, PrintOrderImport
from backend.schemas.print_order import PrintOrderMappingIn, PrintOrderReviewIn
from backend.services.print_order_service import PrintOrderService

router = APIRouter(prefix="/operacoes/print-pedido", tags=["print-pedido"])
view = require_rbac_permission("pedidos", "view")
create = require_rbac_permission("pedidos", "create")
edit = require_rbac_permission("pedidos", "edit")

def svc(db, actor): return PrintOrderService(db, actor.tenant_id, actor.user_id, actor.tenant_context)
def call(fn, *args):
    try: return fn(*args)
    except DomainError as exc: return err(exc)

@router.post("/imports", status_code=201)
async def capture(file: UploadFile = File(...), platform: str | None = Form(None), extracted_text: str | None = Form(None), db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(create)):
    return await _capture(db, actor, file, platform, extracted_text)

async def _capture(db, actor, file, platform, extracted_text):
    try: return created(svc(db, actor).serialize(await svc(db, actor).capture(file, platform, extracted_text)))
    except DomainError as exc: return err(exc)

@router.get("/imports")
def list_imports(db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(view)):
    service = svc(db, actor); rows = db.query(PrintOrderImport).filter_by(tenant_id=actor.tenant_id).order_by(PrintOrderImport.created_at.desc()).limit(200).all(); return ok([service.serialize(r) for r in rows])

@router.get("/imports/{import_id}")
def get_import(import_id: str, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(view)): return call(lambda: ok(svc(db, actor).serialize(svc(db, actor)._get(import_id))))

@router.patch("/imports/{import_id}")
def review(import_id: str, body: PrintOrderReviewIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(edit)): return call(lambda: ok(svc(db, actor).serialize(svc(db, actor).review(import_id, body))))

@router.post("/imports/{import_id}/confirm")
def confirm(import_id: str, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(create), key: str = Header(..., alias="Idempotency-Key", min_length=1, max_length=200)): return call(lambda: ok(svc(db, actor).serialize(svc(db, actor).confirm(import_id, key))))

@router.get("/mappings")
def mappings(db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(view)): return ok([{k: v for k, v in m.__dict__.items() if not k.startswith("_")} for m in db.query(PrintOrderCatalogMapping).filter_by(tenant_id=actor.tenant_id).all()])

@router.post("/mappings", status_code=201)
def create_mapping(body: PrintOrderMappingIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(edit)):
    def create_payload():
        row = svc(db, actor).mapping(body)
        return created({k: v for k, v in row.__dict__.items() if not k.startswith("_")})
    return call(create_payload)
