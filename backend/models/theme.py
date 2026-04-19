from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, String

from backend.database import Base


class ThemeSettings(Base):
    __tablename__ = "theme_settings"

    id = Column(String, primary_key=True, default="default")

    # Brand
    primary             = Column(String(20), nullable=False, default="#f97316")
    secondary           = Column(String(20), nullable=False, default="#2d3d56")

    # Backgrounds
    background_main     = Column(String(20), nullable=False, default="#0c1220")
    background_alt      = Column(String(20), nullable=False, default="#111827")
    background_card     = Column(String(20), nullable=False, default="#1e2a3b")

    # Texts
    text_primary        = Column(String(20), nullable=False, default="#f8fafc")
    text_secondary      = Column(String(20), nullable=False, default="#e2e8f0")
    text_muted          = Column(String(20), nullable=False, default="#94a3b8")

    # Status
    status_success      = Column(String(20), nullable=False, default="#22c55e")
    status_error        = Column(String(20), nullable=False, default="#ef4444")
    status_warning      = Column(String(20), nullable=False, default="#f59e0b")
    status_info         = Column(String(20), nullable=False, default="#3b82f6")

    # Border
    border              = Column(String(20), nullable=False, default="#2d3d56")

    # Interactions
    interaction_hover   = Column(String(20), nullable=False, default="#fb923c")
    interaction_active  = Column(String(20), nullable=False, default="#ea6f10")
    interaction_focus   = Column(String(20), nullable=False, default="#f97316")

    # Structure
    navbar              = Column(String(20), nullable=False, default="#111827")
    footer              = Column(String(20), nullable=False, default="#0c1220")
    sidebar             = Column(String(20), nullable=False, default="#111827")
    modal               = Column(String(20), nullable=False, default="#1e2a3b")
    overlay             = Column(String(20), nullable=False, default="#000000")
    badge               = Column(String(20), nullable=False, default="#f97316")
    tag                 = Column(String(20), nullable=False, default="#2d3d56")

    created_at          = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at          = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                                 onupdate=lambda: datetime.now(timezone.utc))
