"""
PizzaApp — FastAPI backend entry point.

Start with:
    uvicorn backend.main:app --reload --port 8000

Or directly:
    python -m backend.main
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.config import get_settings
from backend.database import create_all_tables, SessionLocal, engine
from backend.routes import products, orders, payments, shipping, coupons, loyalty, customers, promotions, admin, delivery, auth, admin_auth, campaigns, webhooks
from backend.routes import chatbot as chatbot_routes, admin_chatbot as admin_chatbot_routes
from backend.routes import upload as upload_routes
from backend.routes import theme as theme_routes
from backend.routes import home_config as home_config_routes

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
    """Idempotent schema migrations — runs on every startup.

    Each statement runs in its own connection+transaction so a single failure
    never poisons the PostgreSQL session and aborts all subsequent migrations.
    """
    os.makedirs("uploads", exist_ok=True)

    from sqlalchemy import text
    stmts = [
        # ── Existing migrations ───────────────────────────────────────────
        "ALTER TABLE coupons ADD COLUMN IF NOT EXISTS max_uses_per_customer INTEGER",
        "ALTER TABLE coupons ADD COLUMN IF NOT EXISTS campaign_id VARCHAR REFERENCES campaigns(id) ON DELETE SET NULL",
        "ALTER TABLE products ALTER COLUMN icon TYPE TEXT",
        "ALTER TABLE products ADD COLUMN IF NOT EXISTS category VARCHAR(100)",
        "ALTER TABLE promotions ALTER COLUMN icon TYPE TEXT",
        "ALTER TABLE promotions ADD COLUMN IF NOT EXISTS validity_text VARCHAR(200)",
        # ── Product sizes ─────────────────────────────────────────────────
        "CREATE TABLE IF NOT EXISTS product_sizes (id VARCHAR PRIMARY KEY, product_id VARCHAR NOT NULL REFERENCES products(id) ON DELETE CASCADE, label VARCHAR(50) NOT NULL, description VARCHAR(200), price FLOAT NOT NULL, is_default BOOLEAN DEFAULT FALSE, sort_order INTEGER DEFAULT 0, active BOOLEAN DEFAULT TRUE, created_at TIMESTAMPTZ DEFAULT NOW())",
        # ── Chatbot tables (fallback if create_all_tables fails) ──────────
        "CREATE TABLE IF NOT EXISTS chatbot_settings (id VARCHAR PRIMARY KEY DEFAULT 'default', ativo BOOLEAN DEFAULT TRUE, nome_bot VARCHAR(100) DEFAULT 'Assistente', mensagem_inicial TEXT DEFAULT 'Olá! Como posso ajudar?', cor_primaria VARCHAR(20) DEFAULT '#f97316', posicao_widget VARCHAR(20) DEFAULT 'bottom-right', horario_funcionamento TEXT, mensagem_fora_horario TEXT DEFAULT 'Estamos fora do horário de atendimento.', tempo_disparo_auto INTEGER DEFAULT 0, fallback_humano_ativo BOOLEAN DEFAULT TRUE, provedor_ia VARCHAR(20) DEFAULT 'claude', modelo_ia VARCHAR(100) DEFAULT 'claude-sonnet-4-6', temperatura FLOAT DEFAULT 0.7, max_tokens INTEGER DEFAULT 1024, prompt_base TEXT DEFAULT '', regras_fixas TEXT DEFAULT '', tom_de_voz TEXT DEFAULT '', objetivo TEXT DEFAULT '', instrucoes_transferencia TEXT DEFAULT '', limitacoes_proibicoes TEXT DEFAULT '', updated_at TIMESTAMPTZ DEFAULT NOW())",
        "CREATE TABLE IF NOT EXISTS chatbot_faq (id VARCHAR PRIMARY KEY, pergunta TEXT NOT NULL, resposta TEXT NOT NULL, categoria VARCHAR(100) DEFAULT 'geral', prioridade INTEGER DEFAULT 0, ativo BOOLEAN DEFAULT TRUE, vinculo_produto_id VARCHAR REFERENCES products(id) ON DELETE SET NULL, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())",
        "ALTER TABLE chatbot_faq ADD COLUMN IF NOT EXISTS busca_vetor TSVECTOR",
        "CREATE TABLE IF NOT EXISTS chatbot_conversations (id VARCHAR PRIMARY KEY, session_id VARCHAR UNIQUE NOT NULL, cliente_id VARCHAR REFERENCES customers(id) ON DELETE SET NULL, visitor_fingerprint VARCHAR(100), pagina_origem VARCHAR(500), user_agent TEXT, ip_hash VARCHAR(64), status VARCHAR(20) DEFAULT 'aberta', tags TEXT, iniciada_em TIMESTAMPTZ DEFAULT NOW(), encerrada_em TIMESTAMPTZ, assumida_por_user_id VARCHAR REFERENCES admin_users(id) ON DELETE SET NULL, intencao_detectada VARCHAR(200), resumo_conversa TEXT)",
        "CREATE TABLE IF NOT EXISTS chatbot_messages (id VARCHAR PRIMARY KEY, conversation_id VARCHAR NOT NULL REFERENCES chatbot_conversations(id) ON DELETE CASCADE, sender VARCHAR(20) NOT NULL, mensagem TEXT NOT NULL, tipo VARCHAR(20) DEFAULT 'text', tokens_consumidos INTEGER, provedor_usado VARCHAR(50), latencia_ms INTEGER, timestamp TIMESTAMPTZ DEFAULT NOW(), metadata_json TEXT)",
        "CREATE TABLE IF NOT EXISTS chatbot_handoffs (id VARCHAR PRIMARY KEY, conversation_id VARCHAR NOT NULL REFERENCES chatbot_conversations(id) ON DELETE CASCADE, admin_user_id VARCHAR REFERENCES admin_users(id) ON DELETE SET NULL, motivo TEXT, assumido_em TIMESTAMPTZ DEFAULT NOW(), encerrado_em TIMESTAMPTZ)",
        "CREATE TABLE IF NOT EXISTS chatbot_knowledge_docs (id VARCHAR PRIMARY KEY, titulo VARCHAR(200) NOT NULL, conteudo TEXT NOT NULL, categoria VARCHAR(100) DEFAULT 'geral', ativo BOOLEAN DEFAULT TRUE, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())",
        "CREATE TABLE IF NOT EXISTS chatbot_automations (id VARCHAR PRIMARY KEY, nome VARCHAR(200) NOT NULL, gatilho VARCHAR(50) NOT NULL, condicao_json TEXT, mensagem TEXT NOT NULL, ativo BOOLEAN DEFAULT TRUE, delay_segundos INTEGER DEFAULT 0, created_at TIMESTAMPTZ DEFAULT NOW())",
        # ── GIN index for FAQ full-text search (optional, best-effort) ────
        "CREATE INDEX IF NOT EXISTS ix_chatbot_faq_busca_vetor ON chatbot_faq USING gin (busca_vetor) WHERE busca_vetor IS NOT NULL",
        # ── Theme settings ────────────────────────────────────────────────
        'CREATE TABLE IF NOT EXISTS theme_settings (id VARCHAR PRIMARY KEY DEFAULT \'default\', "primary" VARCHAR(20) NOT NULL DEFAULT \'#f97316\', secondary VARCHAR(20) NOT NULL DEFAULT \'#2d3d56\', background_main VARCHAR(20) NOT NULL DEFAULT \'#0c1220\', background_alt VARCHAR(20) NOT NULL DEFAULT \'#111827\', background_card VARCHAR(20) NOT NULL DEFAULT \'#1e2a3b\', text_primary VARCHAR(20) NOT NULL DEFAULT \'#f8fafc\', text_secondary VARCHAR(20) NOT NULL DEFAULT \'#e2e8f0\', text_muted VARCHAR(20) NOT NULL DEFAULT \'#94a3b8\', status_success VARCHAR(20) NOT NULL DEFAULT \'#22c55e\', status_error VARCHAR(20) NOT NULL DEFAULT \'#ef4444\', status_warning VARCHAR(20) NOT NULL DEFAULT \'#f59e0b\', status_info VARCHAR(20) NOT NULL DEFAULT \'#3b82f6\', border VARCHAR(20) NOT NULL DEFAULT \'#2d3d56\', interaction_hover VARCHAR(20) NOT NULL DEFAULT \'#fb923c\', interaction_active VARCHAR(20) NOT NULL DEFAULT \'#ea6f10\', interaction_focus VARCHAR(20) NOT NULL DEFAULT \'#f97316\', navbar VARCHAR(20) NOT NULL DEFAULT \'#111827\', footer VARCHAR(20) NOT NULL DEFAULT \'#0c1220\', sidebar VARCHAR(20) NOT NULL DEFAULT \'#111827\', modal VARCHAR(20) NOT NULL DEFAULT \'#1e2a3b\', overlay VARCHAR(20) NOT NULL DEFAULT \'#000000\', badge VARCHAR(20) NOT NULL DEFAULT \'#f97316\', tag VARCHAR(20) NOT NULL DEFAULT \'#2d3d56\', home_banner_background VARCHAR(20) NOT NULL DEFAULT \'#1f2937\', created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())',
        "INSERT INTO theme_settings (id) VALUES ('default') ON CONFLICT DO NOTHING",
        "ALTER TABLE theme_settings ADD COLUMN IF NOT EXISTS home_banner_background VARCHAR(20) NOT NULL DEFAULT '#1f2937'",
        # ── Chatbot automations: corrige mismatch de colunas da migration original ─
        # A migration criou condicao_json/delay_segundos; o modelo usa condicao/prioridade/updated_at
        "ALTER TABLE chatbot_automations ADD COLUMN IF NOT EXISTS condicao TEXT DEFAULT '{}'",
        "ALTER TABLE chatbot_automations ADD COLUMN IF NOT EXISTS prioridade INTEGER DEFAULT 0",
        "ALTER TABLE chatbot_automations ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()",
        # Chatbot handoffs: migration usou admin_user_id, modelo usa operador_id
        "ALTER TABLE chatbot_handoffs ADD COLUMN IF NOT EXISTS operador_id VARCHAR REFERENCES admin_users(id) ON DELETE SET NULL",
        # Chatbot knowledge docs: migration não incluiu busca_vetor
        "ALTER TABLE chatbot_knowledge_docs ADD COLUMN IF NOT EXISTS busca_vetor TSVECTOR",
        # ── Product type + crust/drink variant tables ─────────────────────
        "ALTER TABLE products ADD COLUMN IF NOT EXISTS product_type VARCHAR(20)",
        "CREATE TABLE IF NOT EXISTS product_categories (id VARCHAR PRIMARY KEY, name VARCHAR(100) NOT NULL UNIQUE, active BOOLEAN DEFAULT TRUE, sort_order INTEGER DEFAULT 0, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())",
        "CREATE TABLE IF NOT EXISTS product_crust_types (id VARCHAR PRIMARY KEY, product_id VARCHAR NOT NULL REFERENCES products(id) ON DELETE CASCADE, name VARCHAR(100) NOT NULL, price_addition FLOAT DEFAULT 0.0, active BOOLEAN DEFAULT TRUE, sort_order INTEGER DEFAULT 0, created_at TIMESTAMPTZ DEFAULT NOW())",
        "CREATE TABLE IF NOT EXISTS product_drink_variants (id VARCHAR PRIMARY KEY, product_id VARCHAR NOT NULL REFERENCES products(id) ON DELETE CASCADE, name VARCHAR(100) NOT NULL, price_addition FLOAT DEFAULT 0.0, active BOOLEAN DEFAULT TRUE, sort_order INTEGER DEFAULT 0, created_at TIMESTAMPTZ DEFAULT NOW())",
        # ── Order item variation columns ──────────────────────────────────
        "ALTER TABLE order_items ADD COLUMN IF NOT EXISTS selected_crust_type VARCHAR(100)",
        "ALTER TABLE order_items ADD COLUMN IF NOT EXISTS selected_drink_variant VARCHAR(100)",
        "ALTER TABLE order_items ADD COLUMN IF NOT EXISTS notes TEXT",
        # ── Home catalog config ───────────────────────────────────────────
        "CREATE TABLE IF NOT EXISTS home_catalog_config (id VARCHAR PRIMARY KEY DEFAULT 'default', mode VARCHAR(20) NOT NULL DEFAULT 'all', selected_categories TEXT DEFAULT '[]', selected_product_ids TEXT DEFAULT '[]', show_promotions BOOLEAN DEFAULT TRUE, updated_at TIMESTAMPTZ DEFAULT NOW())",
        "INSERT INTO home_catalog_config (id) VALUES ('default') ON CONFLICT DO NOTHING",
        # ── Loyalty Engine Pro — new tables ──────────────────────────────
        "CREATE TABLE IF NOT EXISTS loyalty_benefits (id VARCHAR PRIMARY KEY, level_id VARCHAR NOT NULL REFERENCES loyalty_levels(id) ON DELETE CASCADE, benefit_type VARCHAR(30) NOT NULL, label VARCHAR(200) NOT NULL, description TEXT, value FLOAT DEFAULT 0.0, min_order_value FLOAT DEFAULT 0.0, expires_in_days INTEGER, usage_limit INTEGER DEFAULT 1, stackable BOOLEAN DEFAULT FALSE, active BOOLEAN DEFAULT TRUE, created_at TIMESTAMPTZ DEFAULT NOW())",
        "CREATE TABLE IF NOT EXISTS loyalty_benefit_usage (id VARCHAR PRIMARY KEY, customer_id VARCHAR NOT NULL REFERENCES customers(id) ON DELETE CASCADE, benefit_id VARCHAR NOT NULL REFERENCES loyalty_benefits(id) ON DELETE CASCADE, order_id VARCHAR REFERENCES orders(id) ON DELETE SET NULL, used_at TIMESTAMPTZ DEFAULT NOW())",
        "CREATE TABLE IF NOT EXISTS loyalty_cycles (id VARCHAR PRIMARY KEY, customer_id VARCHAR NOT NULL REFERENCES customers(id) ON DELETE CASCADE, start_date TIMESTAMPTZ NOT NULL, end_date TIMESTAMPTZ NOT NULL, points_earned INTEGER DEFAULT 0, points_used INTEGER DEFAULT 0, points_expired INTEGER DEFAULT 0, points_rolled_over INTEGER DEFAULT 0, level_reached VARCHAR REFERENCES loyalty_levels(id) ON DELETE SET NULL, status VARCHAR(20) DEFAULT 'active', created_at TIMESTAMPTZ DEFAULT NOW(), closed_at TIMESTAMPTZ)",
        "CREATE TABLE IF NOT EXISTS referrals (id VARCHAR PRIMARY KEY, referrer_id VARCHAR NOT NULL REFERENCES customers(id) ON DELETE CASCADE, referred_id VARCHAR REFERENCES customers(id) ON DELETE SET NULL, referral_code VARCHAR(20) UNIQUE NOT NULL, status VARCHAR(20) DEFAULT 'pending', reward_points INTEGER DEFAULT 10, created_at TIMESTAMPTZ DEFAULT NOW(), completed_at TIMESTAMPTZ)",
        # ── Loyalty Engine Pro — extend customer_loyalty ─────────────────
        "ALTER TABLE customer_loyalty ADD COLUMN IF NOT EXISTS cycle_start_date TIMESTAMPTZ",
        "ALTER TABLE customer_loyalty ADD COLUMN IF NOT EXISTS cycle_end_date TIMESTAMPTZ",
        "ALTER TABLE customer_loyalty ADD COLUMN IF NOT EXISTS rollover_points INTEGER DEFAULT 0",
        "ALTER TABLE customer_loyalty ADD COLUMN IF NOT EXISTS lifetime_points INTEGER DEFAULT 0",
        "ALTER TABLE customer_loyalty ADD COLUMN IF NOT EXISTS last_activity_at TIMESTAMPTZ",
        "ALTER TABLE customer_loyalty ADD COLUMN IF NOT EXISTS benefit_expiration_date TIMESTAMPTZ",
        # ── Loyalty transactions — new types ─────────────────────────────
        "ALTER TABLE loyalty_transactions ADD COLUMN IF NOT EXISTS description VARCHAR(300)",
        # Payment Brick / Mercado Pago
        "ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'aguardando_pagamento'",
        "ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'pago'",
        "ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'pagamento_recusado'",
        "ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'pagamento_expirado'",
        "ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'ready_for_pickup'",
        "ALTER TYPE paymentstatus ADD VALUE IF NOT EXISTS 'approved'",
        "ALTER TYPE paymentstatus ADD VALUE IF NOT EXISTS 'rejected'",
        "ALTER TYPE paymentstatus ADD VALUE IF NOT EXISTS 'cancelled'",
        "ALTER TYPE paymentstatus ADD VALUE IF NOT EXISTS 'expired'",
        "ALTER TYPE paymentmethod ADD VALUE IF NOT EXISTS 'debit_card'",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS external_reference VARCHAR(120)",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_orders_external_reference ON orders (external_reference) WHERE external_reference IS NOT NULL",
        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS provider VARCHAR(50) DEFAULT 'mock'",
        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS mercado_pago_payment_id VARCHAR(100)",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_payments_mercado_pago_payment_id ON payments (mercado_pago_payment_id) WHERE mercado_pago_payment_id IS NOT NULL",
        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS external_reference VARCHAR(120)",
        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS raw_response TEXT",
        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()",
        "CREATE TABLE IF NOT EXISTS payment_events (id VARCHAR PRIMARY KEY, provider VARCHAR(50) NOT NULL DEFAULT 'mercado_pago', event_type VARCHAR(100), mercado_pago_payment_id VARCHAR(100), external_reference VARCHAR(120), raw_payload TEXT NOT NULL, processed_at TIMESTAMPTZ, created_at TIMESTAMPTZ DEFAULT NOW())",
    ]
    for stmt in stmts:
        try:
            with engine.connect() as conn:
                conn.execute(text(stmt))
                conn.commit()
        except Exception:
            pass  # IF NOT EXISTS / ON CONFLICT guards make every stmt idempotent


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
app.include_router(chatbot_routes.router)
app.include_router(admin_chatbot_routes.router)
app.include_router(upload_routes.router)
app.include_router(theme_routes.router)
app.include_router(home_config_routes.router)
app.include_router(webhooks.router)

# Backward-compatible /api aliases expected by deployment/proxy setups.
app.include_router(products.router, prefix="/api")
app.include_router(orders.router, prefix="/api")
app.include_router(payments.router, prefix="/api")
app.include_router(shipping.router, prefix="/api")
app.include_router(coupons.router, prefix="/api")
app.include_router(loyalty.router, prefix="/api")
app.include_router(customers.router, prefix="/api")
app.include_router(promotions.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(delivery.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(admin_auth.router, prefix="/api")
app.include_router(campaigns.router, prefix="/api")
app.include_router(chatbot_routes.router, prefix="/api")
app.include_router(admin_chatbot_routes.router, prefix="/api")
app.include_router(upload_routes.router, prefix="/api")
app.include_router(theme_routes.router, prefix="/api")
app.include_router(home_config_routes.router, prefix="/api")
app.include_router(webhooks.router, prefix="/api")

# ── Static files (uploaded images) ───────────────────────────────────────────
# Must be mounted AFTER all route registrations.
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads", html=False), name="uploads")

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
