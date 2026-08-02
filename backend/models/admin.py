from sqlalchemy import Boolean, Column, DateTime, Integer, String
from datetime import datetime, timezone
from backend.database import Base


class AdminUser(Base):
    __tablename__ = "admin_users"

    id             = Column(String, primary_key=True)
    email          = Column(String(200), unique=True, nullable=False)
    name           = Column(String(200), nullable=False)
    password_hash  = Column(String(300), nullable=False)
    active         = Column(Boolean, default=True)
    phone          = Column(String(30), nullable=True)
    role_id        = Column(String(100), nullable=True)   # FK to roles.id (enforced at app level)
    store_id       = Column(String(100), nullable=True)
    last_login_at  = Column(DateTime(timezone=True), nullable=True)
    force_password_change = Column(Boolean, nullable=False, default=False)
    # Zero preserves JWTs issued before this field existed. Any explicit
    # revocation increments the version and invalidates older/missing claims.
    auth_version   = Column(Integer, nullable=False, default=0)
    job_title = Column(String(120), nullable=True)
    created_by     = Column(String, nullable=True)        # FK to admin_users.id
    updated_by     = Column(String, nullable=True)        # FK to admin_users.id
    created_at     = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at     = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                            onupdate=lambda: datetime.now(timezone.utc))
