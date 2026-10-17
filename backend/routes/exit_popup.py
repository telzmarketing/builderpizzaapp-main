"""Exit popup configuration — public GET, admin-only PUT."""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.core.tenant_context import TenantContext
from backend.models.exit_popup import ExitPopupConfig
from backend.core.wave6_tenant_context import panel_wave6_context, public_wave6_context, wave6_tenant_id
from backend.routes.admin_auth import get_current_admin
from backend.services.exit_popup_service import ExitPopupService

router = APIRouter(prefix="/exit-popup", tags=["exit_popup"])


class ExitPopupUpdate(BaseModel):
    enabled: bool | None = None
    title: str | None = None
    subtitle: str | None = None
    coupon_code: str | None = None
    button_text: str | None = None
    image_url: str | None = None
    show_once_per_session: bool | None = None
    trigger_delay_seconds: int | None = None


def _get_or_create(db: Session, tenant_id: str) -> ExitPopupConfig:
    return ExitPopupService(db).get_or_create(tenant_id)


def _to_dict(cfg: ExitPopupConfig) -> dict:
    return {
        "id": cfg.id,
        "enabled": cfg.enabled,
        "title": cfg.title,
        "subtitle": cfg.subtitle,
        "coupon_code": cfg.coupon_code,
        "button_text": cfg.button_text,
        "image_url": cfg.image_url,
        "show_once_per_session": cfg.show_once_per_session,
        "trigger_delay_seconds": cfg.trigger_delay_seconds or 10,
        "updated_at": cfg.updated_at.isoformat() if cfg.updated_at else None,
    }


@router.get("")
def get_exit_popup(
    request: Request,
    db: Session = Depends(get_db),
    context: TenantContext | None = Depends(public_wave6_context),
):
    return _to_dict(_get_or_create(db, wave6_tenant_id(context)))


@router.put("")
def update_exit_popup(
    body: ExitPopupUpdate,
    request: Request,
    db: Session = Depends(get_db),
    context: TenantContext | None = Depends(panel_wave6_context),
    _=Depends(get_current_admin),
):
    cfg = ExitPopupService(db).update(
        wave6_tenant_id(context), body.model_dump(exclude_none=True),
    )
    return _to_dict(cfg)
