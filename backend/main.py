"""
PizzaApp — FastAPI backend entry point.

Start with:
    uvicorn backend.main:app --reload --port 8000

Or directly:
    python -m backend.main
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.config import get_settings
from backend.database import create_all_tables, SessionLocal, engine
from backend.routes import products, orders, payments, shipping, coupons, loyalty, customers, promotions, admin, delivery, auth, admin_auth, campaigns

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────────────────────
    create_all_tables()

    # Run incremental column migrations (safe to run on every start)
    _run_migrations()

    # Seed initial data
    from backend.core.seed import seed_all
    with SessionLocal() as db:
        seed_all(db)

    # Register event bus handlers (ERP sync, push notifications)
    from backend.core.events import (
        bus,
        OrderCreated, OrderStatusChanged, OrderCancelled,
        PaymentConfirmed, DeliveryAssigned, DeliveryCompleted,
        erp_order_created_handler, erp_order_status_handler,
        erp_payment_confirmed_handler, erp_delivery_completed_handler,
        push_notification_handler,
    )
    bus.subscribe(OrderCreated, erp_order_created_handler)
    bus.subscribe(OrderCreated, push_notification_handler)
    bus.subscribe(OrderStatusChanged, erp_order_status_handler)
    bus.subscribe(OrderStatusChanged, push_notification_handler)
    bus.subscribe(PaymentConfirmed, erp_payment_confirmed_handler)
    bus.subscribe(PaymentConfirmed, push_notification_handler)
    bus.subscribe(DeliveryAssigned, push_notification_handler)
    bus.subscribe(DeliveryCompleted, erp_delivery_completed_handler)
    bus.subscribe(DeliveryCompleted, push_notification_handler)

    yield
    # ── Shutdown ──────────────────────────────────────────────────────────────


def _run_migrations():
    """Idempotent schema migrations — runs on every startup."""
    from sqlalchemy import text
    with engine.connect() as conn:
        stmts = [
            "ALTER TABLE coupons ADD COLUMN IF NOT EXISTS max_uses_per_customer INTEGER",
            "ALTER TABLE coupons ADD COLUMN IF NOT EXISTS campaign_id VARCHAR REFERENCES campaigns(id) ON DELETE SET NULL",
            "ALTER TABLE products ALTER COLUMN icon TYPE TEXT",
            "ALTER TABLE products ADD COLUMN IF NOT EXISTS category VARCHAR(100)",
            "ALTER TABLE promotions ALTER COLUMN icon TYPE TEXT",
            "ALTER TABLE promotions ADD COLUMN IF NOT EXISTS validity_text VARCHAR(200)",
        ]
        for stmt in stmts:
            try:
                conn.execute(text(stmt))
            except Exception:
                pass
        conn.commit()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Backend completo para sistema de pedidos de pizzaria com multi-sabor, frete dinâmico e pagamentos.",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(products.router)
app.include_router(orders.router)
app.include_router(payments.router)
app.include_router(shipping.router)
app.include_router(coupons.router)
app.include_router(loyalty.router)
app.include_router(customers.router)
app.include_router(promotions.router)
app.include_router(admin.router)
app.include_router(delivery.router)
app.include_router(auth.router)
app.include_router(admin_auth.router)
app.include_router(campaigns.router)


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["system"])
def health():
    from backend.core.response import ok
    return ok({"status": "ok", "version": settings.APP_VERSION})


# ── Global exception handlers ─────────────────────────────────────────────────

from backend.core.exceptions import DomainError  # noqa: E402

@app.exception_handler(DomainError)
async def domain_error_handler(request, exc: DomainError):
    """Catch any DomainError that escapes a route handler."""
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "success": False,
            "error": {"code": exc.code, "message": exc.message},
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc: Exception):
    """Catch-all for unexpected errors — never expose internals in production."""
    import logging
    logging.getLogger("uvicorn.error").exception("Unhandled error", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {
                "code":    "InternalServerError",
                "message": "Erro interno do servidor. Tente novamente.",
            },
        },
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
