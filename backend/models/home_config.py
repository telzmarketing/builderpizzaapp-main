from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Index, Text
from datetime import datetime, timezone
from backend.database import Base


class HomeCatalogConfig(Base):
    """Singleton config controlling what appears in the home page catalog."""
    __tablename__ = "home_catalog_config"
    __table_args__ = (Index("uq_home_catalog_config_tenant_id_id", "tenant_id", "id", unique=True),)

    id = Column(String, primary_key=True, default="default")
    tenant_id = Column(String, ForeignKey("tenants.id", name="fk_home_catalog_config_tenant_id_tenants"), nullable=True)
    # "all" | "categories" | "products"
    mode = Column(String(20), default="all", nullable=False)
    # JSON array of category name strings
    selected_categories = Column(Text, default="[]")
    # JSON array of product ID strings
    selected_product_ids = Column(Text, default="[]")
    # Whether to include the promotions banner section
    show_promotions = Column(Boolean, default=True)
    updated_at = Column(DateTime(timezone=True),
                        default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
