"""Exit popup configuration — public GET, admin-only PUT."""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import Column, Boolean, Integer, String, Text, DateTime
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from backend.database import get_db, Base
from backend.core.tenant_context import TenantContext
from backend.core.wave6_tenant_orm import wave6_tenant_column
from backend.core.wave6_tenant_context import panel_wave6_context, public_wave6_context, wave6_tenant_id
from backend.routes.admin_auth import get_current_admin

router = APIRouter(prefix="/exit-popup", tags=["exit_popup"])


class ExitPopupConfig(Base):
    __tablename__ = "exit_popup_config"
    tenant_id = wave6_tenant_column("exit_popup_config")
    id = Column(String, primary_key=True, default="default")
    enabled = Column(Boolean, default=False)
    title = Column(String(200), default="Espera! Temos uma oferta para você 🍕")
    subtitle = Column(Text, default="Use o cupom abaixo e ganhe desconto no seu pedido!")
    coupon_code = Column(String(50), nullable=True)
    button_text = Column(String(100), default="Usar cupom agora")
    image_url = Column(Text, nullable=True)
    show_once_per_session = Column(Boolean, default=True)
    trigger_delay_seconds = Column(Integer, default=10)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


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
    config_id = "default" if tenant_id == "default" else f"exit-popup-{tenant_id}"
    cfg = (
        db.query(ExitPopupConfig)
        .filter(ExitPopupConfig.id == config_id, ExitPopupConfig.tenant_id == tenant_id)
        .first()
    )
    if not cfg:
        cfg = ExitPopupConfig(id=config_id, tenant_id=tenant_id)
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


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
    cfg = _get_or_create(db, wave6_tenant_id(context))
    for field, value in body.model_dump(exclude_none=True).items():
        if field == "trigger_delay_seconds":
            value = max(1, min(int(value), 3600))
        setattr(cfg, field, value)
    cfg.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(cfg)
    return _to_dict(cfg)
