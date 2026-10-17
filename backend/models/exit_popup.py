"""Tenant-owned exit popup configuration."""
from datetime import datetime, timezone

from sqlalchemy import Column, Boolean, Integer, String, Text, DateTime

from backend.database import Base
from backend.core.wave6_tenant_orm import wave6_tenant_column


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
