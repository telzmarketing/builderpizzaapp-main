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
from backend.routes import products, orders, payments, shipping, coupons, loyalty, customers, promotions, admin, delivery, auth, admin_auth, campaigns
from backend.routes import chatbot as chatbot_routes, admin_chatbot as admin_chatbot_routes
from backend.routes import upload as upload_routes

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
    os.makedirs("uploads", exist_ok=True)

    from sqlalchemy import text
    with engine.connect() as conn:
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
app.include_router(chatbot_routes.router)
app.include_router(admin_chatbot_routes.router)
app.include_router(upload_routes.router)

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
