"""
Admin-specific endpoints: dashboard stats and payment gateway config.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.core.local_time import local_period_bounds, local_today, to_store_datetime
from backend.database import get_db
from backend.models.order import Order, OrderStatus
from backend.models.product import Product
from backend.models.customer import Customer
from backend.models.payment import Payment, PaymentStatus
from backend.models.payment_config import PaymentGatewayConfig
from backend.models.admin import AdminUser
from backend.config import get_settings
from backend.core.tenant_runtime import resolve_panel_tenant_context
from backend.routes.admin_auth import get_current_admin
from backend.schemas.payment_config import (
    PaymentGatewayConfigOut,
    PaymentGatewayConfigUpdate,
    PaymentGatewayRoutingUpdate,
    PaymentProviderConfigUpdate,
    _mask,
)
from backend.services.payment_gateway_resolver import asaas_credit_card_runtime_available
from backend.services.tenant_credential_service import TenantCredentialService

router = APIRouter(prefix="/admin", tags=["admin"])
LEGACY_TENANT_ID = "tenant-legacy-default"


CONFIRMED_STATUSES = [
    OrderStatus.paid,
    OrderStatus.preparing,
    OrderStatus.ready_for_pickup,
    OrderStatus.on_the_way,
    OrderStatus.delivered,
]

PAID_PAYMENT_STATUSES = [PaymentStatus.approved, PaymentStatus.paid]
WAITING_PAYMENT_STATUSES = [
    OrderStatus.pending,
    OrderStatus.waiting_payment,
    OrderStatus.aguardando_pagamento,
]
NON_EFFECTIVE_ORDER_STATUSES = [OrderStatus.cancelled, OrderStatus.refunded]


@router.get("/dashboard")
def dashboard_stats(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    # Only count confirmed orders (paid or beyond)
    total_orders = (
        db.query(func.count(Order.id))
        .filter(Order.status.in_(CONFIRMED_STATUSES))
        .scalar()
        or 0
    )
    # Waiting payment — shown separately in dashboard
    waiting_payment_orders = (
        db.query(func.count(Order.id))
        .filter(Order.status.in_(WAITING_PAYMENT_STATUSES))
        .scalar()
        or 0
    )
    estimated_revenue = db.query(func.sum(Order.total)).scalar() or 0.0
    effective_revenue = (
        db.query(func.sum(Order.total))
        .join(Payment, Payment.order_id == Order.id)
        .filter(Payment.status.in_(PAID_PAYMENT_STATUSES))
        .filter(~Order.status.in_(NON_EFFECTIVE_ORDER_STATUSES))
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
    from datetime import timedelta
    end_date = local_today()
    start_date = end_date - timedelta(days=6)
    start_dt, end_dt = local_period_bounds(start_date, end_date)
    daily_revenue_rows = (
        db.query(
            Order.id.label("order_id"),
            Order.created_at.label("created_at"),
            Order.total.label("total"),
        )
        .join(Payment, Payment.order_id == Order.id)
        .filter(Payment.status.in_(PAID_PAYMENT_STATUSES))
        .filter(Order.created_at >= start_dt, Order.created_at <= end_dt)
        .filter(~Order.status.in_(NON_EFFECTIVE_ORDER_STATUSES))
        .group_by(Order.id, Order.created_at, Order.total)
        .all()
    )
    daily_estimated_rows = (
        db.query(
            Order.id.label("order_id"),
            Order.created_at.label("created_at"),
            Order.total.label("total"),
        )
        .filter(Order.created_at >= start_dt, Order.created_at <= end_dt)
        .all()
    )

    def _daily_revenue_payload(rows):
        totals: dict[str, float] = {}
        for row in rows:
            day = to_store_datetime(row.created_at).date().isoformat()
            totals[day] = totals.get(day, 0.0) + float(row.total or 0)
        return [
            {
                "day": (start_date + timedelta(days=offset)).isoformat(),
                "revenue": round(totals.get((start_date + timedelta(days=offset)).isoformat(), 0.0), 2),
            }
            for offset in range(7)
        ]

    return {
        "total_orders": total_orders,
        "waiting_payment_orders": waiting_payment_orders,
        "total_revenue": round(effective_revenue, 2),
        "estimated_revenue": round(estimated_revenue, 2),
        "effective_revenue": round(effective_revenue, 2),
        "pending_orders": pending_orders,
        "total_products": total_products,
        "total_customers": total_customers,
        "daily_revenue": _daily_revenue_payload(daily_revenue_rows),
        "daily_estimated_revenue": _daily_revenue_payload(daily_estimated_rows),
    }


# ── Payment gateway config ────────────────────────────────────────────────────

SUPPORTED_PAYMENT_PROVIDERS = {"mercado_pago", "asaas", "pagarme"}


def _normalize_provider(value: str | None) -> str:
    raw = (value or "").strip().lower().replace("-", "_")
    aliases = {
        "mercadopago": "mercado_pago",
        "mp": "mercado_pago",
    }
    provider = aliases.get(raw, raw)
    if provider not in SUPPORTED_PAYMENT_PROVIDERS:
        raise HTTPException(status_code=422, detail=f"Gateway de pagamento invalido: {value}")
    return provider


def _normalize_environment(value: str | None) -> str:
    raw = (value or "").strip().lower()
    if raw in {"prod", "production", "producao"}:
        return "production"
    if raw in {"sandbox", "test", "testing", "teste", ""}:
        return "sandbox"
    raise HTTPException(status_code=422, detail=f"Ambiente de pagamento invalido: {value}")


def _is_truthy(value: object) -> bool:
    return bool(value)


def _provider_ready_for_method(config: PaymentGatewayConfig, provider: str, method: str) -> bool:
    if provider == "mercado_pago":
        if not _is_truthy(config.mp_enabled):
            return False
        if method == "pix":
            return bool(config.mp_pix_enabled and config.mp_access_token)
        if method == "credit_card":
            return bool(config.mp_credit_card_enabled and config.mp_public_key and config.mp_access_token)
    if provider == "asaas":
        if not _is_truthy(config.asaas_enabled):
            return False
        if method == "pix":
            return bool(config.asaas_pix_enabled and config.asaas_api_key)
        if method == "credit_card":
            return bool(
                config.asaas_credit_card_enabled
                and config.asaas_api_key
                and asaas_credit_card_runtime_available()
            )
    if provider == "pagarme":
        if not config.pagarme_enabled or not config.pagarme_secret_key:
            return False
        if method == "pix":
            return bool(config.pagarme_pix_enabled)
        if method == "credit_card":
            return bool(config.pagarme_credit_card_enabled and config.pagarme_public_key)
    return False


def _provider_health(config: PaymentGatewayConfig, provider: str) -> dict:
    if provider == "mercado_pago":
        missing = []
        if not config.mp_public_key:
            missing.append("mp_public_key")
        if not config.mp_access_token:
            missing.append("mp_access_token")
        if not config.mp_webhook_secret:
            missing.append("mp_webhook_secret")
        return {
            "provider": "mercado_pago",
            "enabled": bool(config.mp_enabled),
            "environment": config.mp_environment,
            "configured": not missing,
            "missing": missing,
            "last_health_check_at": config.mp_last_health_check_at,
            "last_health_check_status": config.mp_last_health_check_status,
            "last_health_check_message": config.mp_last_health_check_message,
        }
    if provider == "asaas":
        missing = []
        if not config.asaas_api_key:
            missing.append("asaas_api_key")
        if not config.asaas_webhook_token:
            missing.append("asaas_webhook_token")
        return {
            "provider": "asaas",
            "enabled": bool(config.asaas_enabled),
            "environment": config.asaas_environment,
            "configured": not missing,
            "missing": missing,
            "tokenization_status": config.asaas_tokenization_status,
            "last_health_check_at": config.asaas_last_health_check_at,
            "last_health_check_status": config.asaas_last_health_check_status,
            "last_health_check_message": config.asaas_last_health_check_message,
        }
    if provider == "pagarme":
        missing = []
        if not config.pagarme_public_key:
            missing.append("pagarme_public_key")
        if not config.pagarme_secret_key:
            missing.append("pagarme_secret_key")
        if not config.pagarme_webhook_secret:
            missing.append("pagarme_webhook_secret")
        return {
            "provider": "pagarme", "enabled": bool(config.pagarme_enabled),
            "environment": config.pagarme_environment,
            "configured": not missing, "missing": missing,
            "last_health_check_at": config.pagarme_last_health_check_at,
            "last_health_check_status": config.pagarme_last_health_check_status,
            "last_health_check_message": config.pagarme_last_health_check_message,
        }
    raise HTTPException(status_code=404, detail="Gateway de pagamento nao encontrado.")


def _validate_routing(config: PaymentGatewayConfig, *, methods: set[str] | None = None) -> None:
    pix_provider = _normalize_provider(config.pix_provider)
    credit_card_provider = _normalize_provider(config.credit_card_provider)
    config.pix_provider = pix_provider
    config.credit_card_provider = credit_card_provider
    methods = methods or {"pix", "credit_card"}

    if "pix" in methods and config.accept_pix and not _provider_ready_for_method(config, pix_provider, "pix"):
        raise HTTPException(
            status_code=422,
            detail="Gateway de Pix selecionado nao esta habilitado ou configurado.",
        )
    if (
        "credit_card" in methods
        and config.accept_credit_card
        and not _provider_ready_for_method(config, credit_card_provider, "credit_card")
    ):
        raise HTTPException(
            status_code=422,
            detail="Gateway de cartao selecionado nao esta habilitado ou configurado.",
        )


def _enforce_asaas_card_safety(config: PaymentGatewayConfig) -> None:
    if asaas_credit_card_runtime_available():
        return
    config.asaas_credit_card_enabled = False
    if config.asaas_tokenization_status == "validated":
        config.asaas_tokenization_status = "not_validated"
    if _normalize_provider(config.credit_card_provider or "mercado_pago") == "asaas":
        config.credit_card_provider = "mercado_pago"


def _panel_tenant_id(request: Request, db: Session, admin: AdminUser) -> str:
    context = resolve_panel_tenant_context(request, db, admin)
    return context.tenant_id if context else LEGACY_TENANT_ID


def _get_or_create_config(db: Session, tenant_id: str) -> PaymentGatewayConfig:
    config = TenantCredentialService(db).create_inert_payment_gateway(tenant_id)
    dirty = False
    asaas_card_state = (
        config.asaas_credit_card_enabled,
        config.asaas_tokenization_status,
        config.credit_card_provider,
    )
    _enforce_asaas_card_safety(config)
    if asaas_card_state != (
        config.asaas_credit_card_enabled,
        config.asaas_tokenization_status,
        config.credit_card_provider,
    ):
        dirty = True
    if dirty:
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
        pix_provider=config.pix_provider or "mercado_pago",
        credit_card_provider=config.credit_card_provider or "mercado_pago",
        mp_enabled=bool(config.mp_enabled),
        mp_environment=config.mp_environment or "sandbox",
        mp_public_key=config.mp_public_key,
        mp_access_token_masked=_mask(config.mp_access_token),
        mp_webhook_secret_masked=_mask(config.mp_webhook_secret),
        mp_pix_enabled=bool(config.mp_pix_enabled),
        mp_credit_card_enabled=bool(config.mp_credit_card_enabled),
        mp_max_installments=config.mp_max_installments or 6,
        mp_last_health_check_at=config.mp_last_health_check_at,
        mp_last_health_check_status=config.mp_last_health_check_status or "not_tested",
        mp_last_health_check_message=config.mp_last_health_check_message,
        asaas_enabled=bool(config.asaas_enabled),
        asaas_environment=config.asaas_environment or "sandbox",
        asaas_api_key_masked=_mask(config.asaas_api_key),
        asaas_webhook_token_masked=_mask(config.asaas_webhook_token),
        asaas_pix_enabled=bool(config.asaas_pix_enabled),
        asaas_credit_card_enabled=bool(config.asaas_credit_card_enabled),
        asaas_max_installments=config.asaas_max_installments or 1,
        asaas_tokenization_status=config.asaas_tokenization_status or "not_validated",
        asaas_last_health_check_at=config.asaas_last_health_check_at,
        asaas_last_health_check_status=config.asaas_last_health_check_status or "not_tested",
        asaas_last_health_check_message=config.asaas_last_health_check_message,
        pagarme_enabled=bool(config.pagarme_enabled),
        pagarme_environment=config.pagarme_environment or "sandbox",
        pagarme_public_key=config.pagarme_public_key,
        pagarme_secret_key_masked=_mask(config.pagarme_secret_key),
        pagarme_webhook_secret_masked=_mask(config.pagarme_webhook_secret),
        pagarme_pix_enabled=bool(config.pagarme_pix_enabled),
        pagarme_credit_card_enabled=bool(config.pagarme_credit_card_enabled),
        pagarme_max_installments=config.pagarme_max_installments or 1,
        pagarme_last_health_check_at=config.pagarme_last_health_check_at,
        pagarme_last_health_check_status=config.pagarme_last_health_check_status or "not_tested",
        pagarme_last_health_check_message=config.pagarme_last_health_check_message,
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


def _apply_update(config: PaymentGatewayConfig, data: dict) -> None:
    for key, value in data.items():
        if key in {"pix_provider", "credit_card_provider"} and value is not None:
            value = _normalize_provider(value)
        if key in {"mp_environment", "asaas_environment", "pagarme_environment"} and value is not None:
            value = _normalize_environment(value)
        setattr(config, key, value if value != "" else None)


@router.get("/payment-gateway", response_model=PaymentGatewayConfigOut)
def get_payment_gateway_config(request: Request, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    """Returns current gateway config (secret keys are masked)."""
    return _to_out(_get_or_create_config(db, _panel_tenant_id(request, db, admin)))


@router.put("/payment-gateway", response_model=PaymentGatewayConfigOut)
def update_payment_gateway_config(
    body: PaymentGatewayConfigUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    """
    Updates gateway config. Only non-null fields are written.
    To clear a key, send an empty string "".
    """
    config = _get_or_create_config(db, _panel_tenant_id(request, db, admin))
    data = body.model_dump(exclude_none=True)
    _apply_update(config, data)
    config.gateway = "mercadopago"
    _enforce_asaas_card_safety(config)
    changed_methods = {
        "pix" for key in data if key in {"pix_provider", "accept_pix"}
    } | {
        "credit_card" for key in data if key in {"credit_card_provider", "accept_credit_card"}
    }
    if changed_methods:
        _validate_routing(config, methods=changed_methods)
    db.commit()
    db.refresh(config)
    return _to_out(config)


@router.get("/payment-gateways")
def get_payment_gateways(request: Request, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    config = _get_or_create_config(db, _panel_tenant_id(request, db, admin))
    return {
        "routing": {
            "pix_provider": config.pix_provider or "mercado_pago",
            "credit_card_provider": config.credit_card_provider or "mercado_pago",
        },
        "providers": {
            "mercado_pago": _provider_health(config, "mercado_pago"),
            "asaas": _provider_health(config, "asaas"),
            "pagarme": _provider_health(config, "pagarme"),
        },
        "config": _to_out(config),
    }


@router.put("/payment-gateways/routing", response_model=PaymentGatewayConfigOut)
def update_payment_gateway_routing(
    body: PaymentGatewayRoutingUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    config = _get_or_create_config(db, _panel_tenant_id(request, db, admin))
    data = body.model_dump(exclude_none=True)
    _apply_update(config, data)
    changed_methods = set()
    if "pix_provider" in data:
        changed_methods.add("pix")
    if "credit_card_provider" in data:
        changed_methods.add("credit_card")
    if changed_methods:
        _enforce_asaas_card_safety(config)
        _validate_routing(config, methods=changed_methods)
    db.commit()
    db.refresh(config)
    return _to_out(config)


@router.put("/payment-gateways/{provider}", response_model=PaymentGatewayConfigOut)
def update_payment_gateway_provider(
    provider: str,
    body: PaymentProviderConfigUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    config = _get_or_create_config(db, _panel_tenant_id(request, db, admin))
    provider = _normalize_provider(provider)
    data = body.model_dump(exclude_none=True)
    if provider == "mercado_pago":
        mapping = {
            "enabled": "mp_enabled",
            "environment": "mp_environment",
            "public_key": "mp_public_key",
            "access_token": "mp_access_token",
            "webhook_secret": "mp_webhook_secret",
            "pix_enabled": "mp_pix_enabled",
            "credit_card_enabled": "mp_credit_card_enabled",
            "max_installments": "mp_max_installments",
        }
    elif provider == "asaas":
        mapping = {
            "enabled": "asaas_enabled",
            "environment": "asaas_environment",
            "api_key": "asaas_api_key",
            "webhook_token": "asaas_webhook_token",
            "pix_enabled": "asaas_pix_enabled",
            "credit_card_enabled": "asaas_credit_card_enabled",
            "max_installments": "asaas_max_installments",
            "tokenization_status": "asaas_tokenization_status",
        }
    else:
        mapping = {
            "enabled": "pagarme_enabled", "environment": "pagarme_environment",
            "public_key": "pagarme_public_key", "secret_key": "pagarme_secret_key",
            "webhook_secret": "pagarme_webhook_secret",
            "pix_enabled": "pagarme_pix_enabled",
            "credit_card_enabled": "pagarme_credit_card_enabled",
            "max_installments": "pagarme_max_installments",
        }
    _apply_update(config, {mapping[key]: value for key, value in data.items() if key in mapping})
    _enforce_asaas_card_safety(config)
    if data.get("enabled") is True:
        health = _provider_health(config, provider)
        if not health["configured"]:
            raise HTTPException(
                status_code=422,
                detail="Credenciais obrigatorias ausentes; valide a configuracao antes de ativar.",
            )
        selected_methods = set()
        if config.accept_pix and _normalize_provider(config.pix_provider) == provider:
            selected_methods.add("pix")
        if config.accept_credit_card and _normalize_provider(config.credit_card_provider) == provider:
            selected_methods.add("credit_card")
        if selected_methods:
            _validate_routing(config, methods=selected_methods)
    db.commit()
    db.refresh(config)
    return _to_out(config)


@router.post("/payment-gateways/{provider}/test")
def test_payment_gateway_provider(
    provider: str,
    request: Request,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    config = _get_or_create_config(db, _panel_tenant_id(request, db, admin))
    provider = _normalize_provider(provider)
    health = _provider_health(config, provider)
    status = "connected" if health["configured"] and health["enabled"] else "misconfigured"
    message = "Configuracao local valida." if status == "connected" else "Credenciais obrigatorias ausentes ou gateway desabilitado."
    now = datetime.now(timezone.utc)
    if provider == "mercado_pago":
        config.mp_last_health_check_at = now
        config.mp_last_health_check_status = status
        config.mp_last_health_check_message = message
    elif provider == "asaas":
        config.asaas_last_health_check_at = now
        config.asaas_last_health_check_status = status
        config.asaas_last_health_check_message = message
    else:
        config.pagarme_last_health_check_at = now
        config.pagarme_last_health_check_status = status
        config.pagarme_last_health_check_message = message
    db.commit()
    return {"provider": provider, "status": status, "message": message}


@router.get("/payment-gateways/health")
def get_payment_gateways_health(request: Request, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    config = _get_or_create_config(db, _panel_tenant_id(request, db, admin))
    return {
        "mercado_pago": _provider_health(config, "mercado_pago"),
        "asaas": _provider_health(config, "asaas"),
        "pagarme": _provider_health(config, "pagarme"),
    }
