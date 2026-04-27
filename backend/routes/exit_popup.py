"""Exit popup configuration — public GET, admin-only PUT."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import Column, Boolean, String, Text, DateTime
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from backend.database import get_db, Base
from backend.routes.admin_auth import get_current_admin

router = APIRouter(prefix="/exit-popup", tags=["exit_popup"])


class ExitPopupConfig(Base):
    __tablename__ = "exit_popup_config"
    id = Column(String, primary_key=True, default="default")
    enabled = Column(Boolean, default=False)
    title = Column(String(200), default="Espera! Temos uma oferta para você 🍕")
    subtitle = Column(Text, default="Use o cupom abaixo e ganhe desconto no seu pedido!")
    coupon_code = Column(String(50), nullable=True)
    button_text = Column(String(100), default="Usar cupom agora")
    image_url = Column(Text, nullable=True)
    show_once_per_session = Column(Boolean, default=True)
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


def _get_or_create(db: Session) -> ExitPopupConfig:
    cfg = db.query(ExitPopupConfig).filter(ExitPopupConfig.id == "default").first()
    if not cfg:
        cfg = ExitPopupConfig(id="default")
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
        "updated_at": cfg.updated_at.isoformat() if cfg.updated_at else None,
    }


@router.get("")
def get_exit_popup(db: Session = Depends(get_db)):
    return _to_dict(_get_or_create(db))


@router.put("")
def update_exit_popup(body: ExitPopupUpdate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    cfg = _get_or_create(db)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(cfg, field, value)
    cfg.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(cfg)
    return _to_dict(cfg)
