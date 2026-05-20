from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.routes.admin_auth import get_current_admin
from backend.schemas.salao_page import SalaoPageSettingsOut, SalaoPageSettingsUpdate
from backend.services.salao_page_service import SalaoPageService

router = APIRouter(prefix="/salao/page", tags=["salao-page"])


@router.get("", response_model=SalaoPageSettingsOut)
def get_salao_page_settings(db: Session = Depends(get_db)):
    service = SalaoPageService(db)
    return service.serialize()


@router.put("", response_model=SalaoPageSettingsOut)
def update_salao_page_settings(
    body: SalaoPageSettingsUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    service = SalaoPageService(db)
    settings = service.update(body.model_dump(exclude_unset=True))
    return service.serialize(settings)
