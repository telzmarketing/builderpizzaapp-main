from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.admin import AdminUser
from backend.routes.admin_auth import get_current_admin
from backend.schemas.cmv import CmvOverviewOut
from backend.services.cmv_service import CmvService

router = APIRouter(prefix="/gestao/cmv", tags=["gestao-cmv"])


@router.get("/overview", response_model=CmvOverviewOut)
def overview(db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    return CmvService(db).overview()
