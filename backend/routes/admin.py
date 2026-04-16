"""
Admin-specific endpoints: dashboard stats and payment gateway config.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.database import get_db
from backend.models.order import Order, OrderStatus
from backend.models.product import Product
from backend.models.customer import Customer
from backend.models.payment import Payment, PaymentStatus
from backend.models.payment_config import PaymentGatewayConfig
from backend.schemas.payment_config import (
    PaymentGatewayConfigOut, PaymentGatewayConfigUpdate, _mask
)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/dashboard")
def dashboard_stats(db: Session = Depends(get_db)):
    total_orders = db.query(func.count(Order.id)).scalar() or 0
    total_revenue = (
        db.query(func.sum(Order.total))
        .join(Payment, Payment.order_id == Order.id)
        .filter(Payment.status == PaymentStatus.paid)
        .scalar()
        or 0.0
    )
    pending_orders = (
        db.query(func.count(Order.id))
        .filter(Order.status.in_([OrderStatus.paid, OrderStatus.preparing]))
        .scalar()
        or 0
    )
    total_products = db.query(func.count(Product.id)).filter(Product.active == True).scalar() or 0  # noqa: E712
    total_customers = db.query(func.count(Customer.id)).scalar() or 0

    # Revenue by day (last 7 days)
    from datetime import datetime, timezone, timedelta
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    daily_revenue = (
        db.query(
            func.date(Order.created_at).label("day"),
            func.sum(Order.total).label("revenue"),
        )
        .join(Payment, Payment.order_id == Order.id)
        .filter(Payment.status == PaymentStatus.paid, Order.created_at >= seven_days_ago)
        .group_by(func.date(Order.created_at))
        .all()
    )

    return {
        "total_orders": total_orders,
        "total_revenue": round(total_revenue, 2),
        "pending_orders": pending_orders,
        "total_products": total_products,
        "total_customers": total_customers,
        "daily_revenue": [
            {"day": str(row.day), "revenue": round(row.revenue or 0, 2)}
            for row in daily_revenue
        ],
    }


# ── Payment gateway config ────────────────────────────────────────────────────

def _get_or_create_config(db: Session) -> PaymentGatewayConfig:
    config = db.query(PaymentGatewayConfig).filter(PaymentGatewayConfig.id == "default").first()
    if not config:
        config = PaymentGatewayConfig(id="default")
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


def _to_out(config: PaymentGatewayConfig) -> PaymentGatewayConfigOut:
    """Converts DB model to response schema, masking secret keys."""
    return PaymentGatewayConfigOut(
        id=config.id,
        gateway=config.gateway,
        sandbox=config.sandbox,
        accept_pix=config.accept_pix,
        accept_credit_card=config.accept_credit_card,
        accept_debit_card=config.accept_debit_card,
        accept_cash=config.accept_cash,
        mp_public_key=config.mp_public_key,
        mp_access_token_masked=_mask(config.mp_access_token),
        stripe_publishable_key=config.stripe_publishable_key,
        stripe_secret_key_masked=_mask(config.stripe_secret_key),
        pagseguro_email=config.pagseguro_email,
        pagseguro_token_masked=_mask(config.pagseguro_token),
        pix_key=config.pix_key,
        pix_key_type=config.pix_key_type,
        pix_beneficiary_name=config.pix_beneficiary_name,
        pix_beneficiary_city=config.pix_beneficiary_city,
        updated_at=config.updated_at,
    )


@router.get("/payment-gateway", response_model=PaymentGatewayConfigOut)
def get_payment_gateway_config(db: Session = Depends(get_db)):
    """Returns current gateway config (secret keys are masked)."""
    return _to_out(_get_or_create_config(db))


@router.put("/payment-gateway", response_model=PaymentGatewayConfigOut)
def update_payment_gateway_config(body: PaymentGatewayConfigUpdate, db: Session = Depends(get_db)):
    """
    Updates gateway config. Only non-null fields are written.
    To clear a key, send an empty string "".
    """
    config = _get_or_create_config(db)
    for key, value in body.model_dump(exclude_none=True).items():
        setattr(config, key, value if value != "" else None)
    db.commit()
    db.refresh(config)
    return _to_out(config)
