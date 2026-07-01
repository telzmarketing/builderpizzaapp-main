from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, String, Text

from backend.database import Base


class GestaoModuleSettings(Base):
    __tablename__ = "gestao_module_settings"

    id = Column(String, primary_key=True)
    tenant_id = Column(String(80), nullable=False, default="default", index=True)
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
