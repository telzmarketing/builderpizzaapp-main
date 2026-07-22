"""Append-only audit records for platform and tenant administration."""
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Text
from backend.database import Base


class PlatformAuditLog(Base):
    __tablename__ = "platform_audit_logs"
    __table_args__ = (
        Index("ix_platform_audit_logs_tenant_created", "tenant_id", "created_at"),
        Index("ix_platform_audit_logs_actor_created", "actor_user_id", "created_at"),
        Index("ix_platform_audit_logs_resource", "resource_type", "resource_id"),
    )
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True)
    actor_user_id = Column(String, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True)
    actor_label = Column(String(200), nullable=False)
    actor_role = Column(String(50), nullable=True)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(100), nullable=True)
    resource_id = Column(String(100), nullable=True)
    request_id = Column(String(100), nullable=True, index=True)
    correlation_id = Column(String(100), nullable=True, index=True)
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
