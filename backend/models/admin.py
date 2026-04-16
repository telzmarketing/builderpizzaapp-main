from sqlalchemy import Column, String, Boolean, DateTime
from datetime import datetime, timezone
from backend.database import Base


class AdminUser(Base):
    __tablename__ = "admin_users"

    id            = Column(String, primary_key=True)
    email         = Column(String(200), unique=True, nullable=False)
    name          = Column(String(200), nullable=False)
    password_hash = Column(String(300), nullable=False)
    active        = Column(Boolean, default=True)
    created_at    = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at    = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))
