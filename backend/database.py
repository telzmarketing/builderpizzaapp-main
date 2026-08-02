from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from backend.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


# These tables are owned exclusively by Alembic revisions
# 20260815_master_central_core and 20260816_master_completion. They must not be
# materialized by the legacy startup create_all path before migrations run.
MASTER_CENTRAL_MIGRATION_TABLES = frozenset({
    "tenant_profiles",
    "saas_plans",
    "saas_modules",
    "saas_plan_modules",
    "tenant_subscriptions",
    "tenant_licenses",
    "tenant_license_events",
    "tenant_modules",
    "tenant_billing_profiles",
    "saas_invoices",
    "saas_invoice_items",
    "saas_payments",
    "support_sessions",
    "tenant_invitations",
    "tenant_usage_metrics",
    "tenant_internal_notes",
})


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_all_tables():
    """Create all tables and seed initial data."""
    from backend.models import (  # noqa: F401 — import triggers table registration
        product, order, customer, payment, payment_config,
        shipping, shipping_v2, coupon, loyalty, promotion, delivery, admin, campaign,
        chatbot, theme, home_config, paid_traffic, product_promotion, store_operation,
        customer_event, customer_identity, agente_whatsapp, rbac, crm, business_intelligence, store_notification,
        promotion_landing_page, salao, salao_page, whatsapp_gateway, marketing_intelligence, gestao, inventory, cmv, finance,
        tenant, tenant_domain, membership, platform_rbac, platform_audit,
        platform_saas,
    )
    from backend.routes import whatsapp_marketing as whatsapp_marketing_routes  # noqa: F401
    from backend.routes import automations as automations_routes  # noqa: F401
    legacy_tables = [
        table
        for table in Base.metadata.tables.values()
        if table.name not in MASTER_CENTRAL_MIGRATION_TABLES
    ]
    Base.metadata.create_all(bind=engine, tables=legacy_tables)
