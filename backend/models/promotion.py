from sqlalchemy import Column, String, Boolean, DateTime, Text
from datetime import datetime, timezone
from backend.database import Base


class Promotion(Base):
    __tablename__ = "promotions"

    id = Column(String, primary_key=True)
    title = Column(String(200), nullable=False)
    subtitle = Column(String(300))
    description = Column(Text)
    icon = Column(Text, default="🍕")
    validity_text = Column(String(200), nullable=True)
    active = Column(Boolean, default=False)
    valid_from = Column(DateTime(timezone=True), nullable=True)
    valid_until = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
