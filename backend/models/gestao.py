from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, String, Text

from backend.database import Base


class GestaoModuleSettings(Base):
    __tablename__ = "gestao_module_settings"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", name="fk_gestao_module_settings_tenant"), nullable=True)
    module_key = Column(String(40), nullable=False, index=True)
    title = Column(String(120), nullable=False)
    description = Column(Text, nullable=False, default="")
    enabled = Column(Boolean, nullable=False, default=False)
    status = Column(String(40), nullable=False, default="disabled")
    settings_json = Column(Text, nullable=False, default="{}")
    notes = Column(Text, nullable=False, default="")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    __table_args__ = (
        Index("uq_gestao_module_settings_tenant_id_id", "tenant_id", "id", unique=True),
        Index("uq_mt_gestao_module_settings_key", "tenant_id", "module_key", unique=True),
    )
