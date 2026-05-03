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
        customer_event, rbac, crm, business_intelligence,
    )
    Base.metadata.create_all(bind=engine)
