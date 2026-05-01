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
from backend.routes import products, orders, payments, shipping, coupons, loyalty, customers, promotions, admin, delivery, auth, admin_auth, campaigns, webhooks, store_operation
from backend.routes import chatbot as chatbot_routes, admin_chatbot as admin_chatbot_routes
from backend.routes import upload as upload_routes
from backend.routes import theme as theme_routes
from backend.routes import home_config as home_config_routes
from backend.routes import paid_traffic as paid_traffic_routes
from backend.routes import lgpd as lgpd_routes
from backend.routes import exit_popup as exit_popup_routes
from backend.routes import admin_users as admin_users_routes
from backend.routes import crm as crm_routes
from backend.routes import marketing as marketing_routes
from backend.routes import whatsapp_marketing as whatsapp_marketing_routes
from backend.routes import email_marketing as email_marketing_routes
from backend.routes import automations as automations_routes
from backend.routes import ads_oauth as ads_oauth_routes
from backend.routes import marketing_workflow as marketing_workflow_routes
from backend.routes import rbac as rbac_routes
from backend.routes import customer_events as customer_events_routes

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
        "ALTER TABLE products ADD COLUMN IF NOT EXISTS subcategory VARCHAR(100)",
        "ALTER TABLE promotions ALTER COLUMN icon TYPE TEXT",
        "ALTER TABLE promotions ADD COLUMN IF NOT EXISTS validity_text VARCHAR(200)",
        # ── Product sizes ─────────────────────────────────────────────────
        "CREATE TABLE IF NOT EXISTS product_sizes (id VARCHAR PRIMARY KEY, product_id VARCHAR NOT NULL REFERENCES products(id) ON DELETE CASCADE, label VARCHAR(50) NOT NULL, description VARCHAR(200), price FLOAT NOT NULL, is_default BOOLEAN DEFAULT FALSE, sort_order INTEGER DEFAULT 0, active BOOLEAN DEFAULT TRUE, created_at TIMESTAMPTZ DEFAULT NOW())",
        "UPDATE product_sizes SET label = 'Pizza Broto', description = '25cm - 4 pedaços' WHERE LOWER(label) IN ('brotinho', 'pizza broto')",
        "UPDATE product_sizes SET description = '35cm - 8 pedaços' WHERE LOWER(label) = 'pizza grande'",
        # ── Chatbot tables (fallback if create_all_tables fails) ──────────
        "CREATE TABLE IF NOT EXISTS chatbot_settings (id VARCHAR PRIMARY KEY DEFAULT 'default', ativo BOOLEAN DEFAULT TRUE, nome_bot VARCHAR(100) DEFAULT 'Assistente', mensagem_inicial TEXT DEFAULT 'Olá! Como posso ajudar?', cor_primaria VARCHAR(20) DEFAULT '#f97316', posicao_widget VARCHAR(20) DEFAULT 'bottom-right', horario_funcionamento TEXT, mensagem_fora_horario TEXT DEFAULT 'Estamos fora do horário de atendimento.', tempo_disparo_auto INTEGER DEFAULT 0, fallback_humano_ativo BOOLEAN DEFAULT TRUE, provedor_ia VARCHAR(20) DEFAULT 'claude', modelo_ia VARCHAR(100) DEFAULT 'claude-sonnet-4-20250514', temperatura FLOAT DEFAULT 0.7, max_tokens INTEGER DEFAULT 1024, prompt_base TEXT DEFAULT '', regras_fixas TEXT DEFAULT '', tom_de_voz TEXT DEFAULT '', objetivo TEXT DEFAULT '', instrucoes_transferencia TEXT DEFAULT '', limitacoes_proibicoes TEXT DEFAULT '', updated_at TIMESTAMPTZ DEFAULT NOW())",
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
        # chatbot_messages: migration criou metadata_json mas modelo usa contexto_usado
        "ALTER TABLE chatbot_messages ADD COLUMN IF NOT EXISTS contexto_usado TEXT",
        # Chatbot handoffs: migration usou admin_user_id, modelo usa operador_id
        "ALTER TABLE chatbot_handoffs ADD COLUMN IF NOT EXISTS operador_id VARCHAR REFERENCES admin_users(id) ON DELETE SET NULL",
        # Chatbot knowledge docs: migration não incluiu busca_vetor
        "ALTER TABLE chatbot_knowledge_docs ADD COLUMN IF NOT EXISTS busca_vetor TSVECTOR",
        # ── Product type + crust/drink variant tables ─────────────────────
        "ALTER TABLE products ADD COLUMN IF NOT EXISTS product_type VARCHAR(20)",
        "CREATE TABLE IF NOT EXISTS product_categories (id VARCHAR PRIMARY KEY, name VARCHAR(100) NOT NULL UNIQUE, active BOOLEAN DEFAULT TRUE, sort_order INTEGER DEFAULT 0, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())",
        "ALTER TABLE product_categories ADD COLUMN IF NOT EXISTS parent_id VARCHAR REFERENCES product_categories(id) ON DELETE CASCADE",
        "CREATE INDEX IF NOT EXISTS ix_product_categories_parent_id ON product_categories(parent_id)",
        "CREATE TABLE IF NOT EXISTS product_crust_types (id VARCHAR PRIMARY KEY, product_id VARCHAR NOT NULL REFERENCES products(id) ON DELETE CASCADE, name VARCHAR(100) NOT NULL, price_addition FLOAT DEFAULT 0.0, active BOOLEAN DEFAULT TRUE, sort_order INTEGER DEFAULT 0, created_at TIMESTAMPTZ DEFAULT NOW())",
        "CREATE TABLE IF NOT EXISTS product_drink_variants (id VARCHAR PRIMARY KEY, product_id VARCHAR NOT NULL REFERENCES products(id) ON DELETE CASCADE, name VARCHAR(100) NOT NULL, price_addition FLOAT DEFAULT 0.0, active BOOLEAN DEFAULT TRUE, sort_order INTEGER DEFAULT 0, created_at TIMESTAMPTZ DEFAULT NOW())",
        "CREATE TABLE IF NOT EXISTS product_promotions (id VARCHAR PRIMARY KEY, product_id VARCHAR NOT NULL REFERENCES products(id) ON DELETE CASCADE, name VARCHAR(200) NOT NULL, active BOOLEAN DEFAULT TRUE, valid_weekdays TEXT NOT NULL DEFAULT '[]', start_time VARCHAR(5), end_time VARCHAR(5), start_date DATE, end_date DATE, discount_type VARCHAR(30) NOT NULL DEFAULT 'fixed_price', default_value FLOAT, timezone VARCHAR(80) NOT NULL DEFAULT 'America/Sao_Paulo', created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())",
        "CREATE INDEX IF NOT EXISTS ix_product_promotions_product_id ON product_promotions(product_id)",
        "CREATE TABLE IF NOT EXISTS product_promotion_combinations (id VARCHAR PRIMARY KEY, promotion_id VARCHAR NOT NULL REFERENCES product_promotions(id) ON DELETE CASCADE, product_size_id VARCHAR REFERENCES product_sizes(id) ON DELETE CASCADE, product_crust_type_id VARCHAR REFERENCES product_crust_types(id) ON DELETE CASCADE, active BOOLEAN DEFAULT TRUE, promotional_value FLOAT, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW(), CONSTRAINT uq_product_promotion_combination UNIQUE (promotion_id, product_size_id, product_crust_type_id))",
        "CREATE INDEX IF NOT EXISTS ix_product_promotion_combinations_promotion_id ON product_promotion_combinations(promotion_id)",
        "CREATE INDEX IF NOT EXISTS ix_product_promotion_combinations_product_size_id ON product_promotion_combinations(product_size_id)",
        "CREATE INDEX IF NOT EXISTS ix_product_promotion_combinations_product_crust_type_id ON product_promotion_combinations(product_crust_type_id)",
        # ── Order item variation columns ──────────────────────────────────
        "ALTER TABLE order_items ADD COLUMN IF NOT EXISTS selected_size_id VARCHAR",
        "ALTER TABLE order_items ADD COLUMN IF NOT EXISTS selected_crust_type_id VARCHAR",
        "ALTER TABLE order_items ADD COLUMN IF NOT EXISTS flavor_count INTEGER DEFAULT 1",
        "ALTER TABLE order_items ADD COLUMN IF NOT EXISTS selected_crust_type VARCHAR(100)",
        "ALTER TABLE order_items ADD COLUMN IF NOT EXISTS selected_drink_variant VARCHAR(100)",
        "ALTER TABLE order_items ADD COLUMN IF NOT EXISTS notes TEXT",
        "ALTER TABLE order_items ADD COLUMN IF NOT EXISTS standard_unit_price FLOAT",
        "ALTER TABLE order_items ADD COLUMN IF NOT EXISTS applied_unit_price FLOAT",
        "ALTER TABLE order_items ADD COLUMN IF NOT EXISTS promotion_id VARCHAR",
        "ALTER TABLE order_items ADD COLUMN IF NOT EXISTS promotion_name VARCHAR(200)",
        "ALTER TABLE order_items ADD COLUMN IF NOT EXISTS promotion_discount FLOAT DEFAULT 0",
        "ALTER TABLE order_items ADD COLUMN IF NOT EXISTS promotion_blocked BOOLEAN DEFAULT FALSE",
        "ALTER TABLE order_items ADD COLUMN IF NOT EXISTS promotion_block_reason VARCHAR(300)",
        # ── Home catalog config ───────────────────────────────────────────
        "CREATE TABLE IF NOT EXISTS home_catalog_config (id VARCHAR PRIMARY KEY DEFAULT 'default', mode VARCHAR(20) NOT NULL DEFAULT 'all', selected_categories TEXT DEFAULT '[]', selected_product_ids TEXT DEFAULT '[]', show_promotions BOOLEAN DEFAULT TRUE, updated_at TIMESTAMPTZ DEFAULT NOW())",
        "INSERT INTO home_catalog_config (id) VALUES ('default') ON CONFLICT DO NOTHING",
        # ── Loyalty Engine Pro — new tables ──────────────────────────────
        "CREATE TABLE IF NOT EXISTS loyalty_benefits (id VARCHAR PRIMARY KEY, level_id VARCHAR NOT NULL REFERENCES loyalty_levels(id) ON DELETE CASCADE, benefit_type VARCHAR(30) NOT NULL, label VARCHAR(200) NOT NULL, description TEXT, value FLOAT DEFAULT 0.0, min_order_value FLOAT DEFAULT 0.0, expires_in_days INTEGER, usage_limit INTEGER DEFAULT 1, stackable BOOLEAN DEFAULT FALSE, active BOOLEAN DEFAULT TRUE, created_at TIMESTAMPTZ DEFAULT NOW())",
        "CREATE TABLE IF NOT EXISTS loyalty_benefit_usage (id VARCHAR PRIMARY KEY, customer_id VARCHAR NOT NULL REFERENCES customers(id) ON DELETE CASCADE, benefit_id VARCHAR NOT NULL REFERENCES loyalty_benefits(id) ON DELETE CASCADE, order_id VARCHAR REFERENCES orders(id) ON DELETE SET NULL, used_at TIMESTAMPTZ DEFAULT NOW())",
        "CREATE TABLE IF NOT EXISTS loyalty_cycles (id VARCHAR PRIMARY KEY, customer_id VARCHAR NOT NULL REFERENCES customers(id) ON DELETE CASCADE, start_date TIMESTAMPTZ NOT NULL, end_date TIMESTAMPTZ NOT NULL, points_earned INTEGER DEFAULT 0, points_used INTEGER DEFAULT 0, points_expired INTEGER DEFAULT 0, points_rolled_over INTEGER DEFAULT 0, level_reached VARCHAR REFERENCES loyalty_levels(id) ON DELETE SET NULL, status VARCHAR(20) DEFAULT 'active', created_at TIMESTAMPTZ DEFAULT NOW(), closed_at TIMESTAMPTZ)",
        "CREATE TABLE IF NOT EXISTS referrals (id VARCHAR PRIMARY KEY, referrer_id VARCHAR NOT NULL REFERENCES customers(id) ON DELETE CASCADE, referred_id VARCHAR REFERENCES customers(id) ON DELETE SET NULL, referral_code VARCHAR(20) UNIQUE NOT NULL, status VARCHAR(20) DEFAULT 'pending', reward_points INTEGER DEFAULT 10, created_at TIMESTAMPTZ DEFAULT NOW(), completed_at TIMESTAMPTZ)",
        "CREATE TABLE IF NOT EXISTS loyalty_settings (id VARCHAR PRIMARY KEY DEFAULT 'default', enabled BOOLEAN NOT NULL DEFAULT TRUE, points_per_real FLOAT NOT NULL DEFAULT 1.0, updated_at TIMESTAMPTZ DEFAULT NOW())",
        "INSERT INTO loyalty_settings (id, enabled, points_per_real) VALUES ('default', TRUE, 1.0) ON CONFLICT DO NOTHING",
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
        # Paid traffic attribution
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS campaign_id VARCHAR REFERENCES traffic_campaigns(id) ON DELETE SET NULL",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS utm_source VARCHAR(100)",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS utm_medium VARCHAR(100)",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS utm_campaign VARCHAR(200)",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS utm_content VARCHAR(200)",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS utm_term VARCHAR(200)",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS session_id VARCHAR(120)",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS landing_page TEXT",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS referrer TEXT",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS is_scheduled BOOLEAN DEFAULT FALSE",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS scheduled_for TIMESTAMPTZ",
        "CREATE INDEX IF NOT EXISTS ix_orders_campaign_id ON orders(campaign_id)",
        "CREATE INDEX IF NOT EXISTS ix_orders_session_id ON orders(session_id)",
        "CREATE INDEX IF NOT EXISTS ix_orders_utm_campaign ON orders(utm_campaign)",
        "INSERT INTO campaign_settings (id) VALUES ('default') ON CONFLICT DO NOTHING",
        "CREATE TABLE IF NOT EXISTS store_operation_settings (id VARCHAR PRIMARY KEY DEFAULT 'default', tenant_id VARCHAR(80) NOT NULL DEFAULT 'default', manual_mode VARCHAR(30) NOT NULL DEFAULT 'manual_open', closed_message TEXT NOT NULL DEFAULT 'Loja fechada no momento.', allow_scheduled_orders BOOLEAN DEFAULT FALSE, timezone VARCHAR(80) NOT NULL DEFAULT 'America/Sao_Paulo', created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())",
        "CREATE INDEX IF NOT EXISTS ix_store_operation_settings_tenant_id ON store_operation_settings(tenant_id)",
        "CREATE TABLE IF NOT EXISTS store_weekly_schedules (id VARCHAR PRIMARY KEY, tenant_id VARCHAR(80) NOT NULL DEFAULT 'default', weekday INTEGER NOT NULL, active BOOLEAN DEFAULT TRUE, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())",
        "CREATE INDEX IF NOT EXISTS ix_store_weekly_schedules_tenant_id ON store_weekly_schedules(tenant_id)",
        "CREATE INDEX IF NOT EXISTS ix_store_weekly_schedules_weekday ON store_weekly_schedules(weekday)",
        "CREATE TABLE IF NOT EXISTS store_operation_intervals (id VARCHAR PRIMARY KEY, schedule_id VARCHAR NOT NULL REFERENCES store_weekly_schedules(id) ON DELETE CASCADE, tenant_id VARCHAR(80) NOT NULL DEFAULT 'default', open_time TIME NOT NULL, close_time TIME NOT NULL, created_at TIMESTAMPTZ DEFAULT NOW())",
        "CREATE INDEX IF NOT EXISTS ix_store_operation_intervals_schedule_id ON store_operation_intervals(schedule_id)",
        "CREATE INDEX IF NOT EXISTS ix_store_operation_intervals_tenant_id ON store_operation_intervals(tenant_id)",
        "CREATE TABLE IF NOT EXISTS store_operation_exceptions (id VARCHAR PRIMARY KEY, tenant_id VARCHAR(80) NOT NULL DEFAULT 'default', date DATE NOT NULL, exception_type VARCHAR(30) NOT NULL, open_time TIME, close_time TIME, reason TEXT, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())",
        "CREATE INDEX IF NOT EXISTS ix_store_operation_exceptions_tenant_id ON store_operation_exceptions(tenant_id)",
        "CREATE INDEX IF NOT EXISTS ix_store_operation_exceptions_date ON store_operation_exceptions(date)",
        "CREATE TABLE IF NOT EXISTS store_operation_logs (id VARCHAR PRIMARY KEY, tenant_id VARCHAR(80) NOT NULL DEFAULT 'default', admin_id VARCHAR, admin_email VARCHAR(200), action VARCHAR(80) NOT NULL, entity VARCHAR(80) NOT NULL, entity_id VARCHAR, old_value TEXT, new_value TEXT, created_at TIMESTAMPTZ DEFAULT NOW())",
        "CREATE INDEX IF NOT EXISTS ix_store_operation_logs_tenant_id ON store_operation_logs(tenant_id)",
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS google_id VARCHAR(200)",
        "ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS active_days VARCHAR(20)",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_customers_google_id ON customers(google_id) WHERE google_id IS NOT NULL",
        # ── LGPD consent fields on customers ─────────────────────────────
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS lgpd_consent BOOLEAN DEFAULT FALSE",
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS lgpd_consent_at TIMESTAMPTZ",
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS lgpd_policy_version VARCHAR(20)",
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS marketing_email_consent BOOLEAN DEFAULT FALSE",
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS marketing_whatsapp_consent BOOLEAN DEFAULT FALSE",
        # ── Address label ─────────────────────────────────────────────────
        "ALTER TABLE addresses ADD COLUMN IF NOT EXISTS label VARCHAR(100)",
        # ── LGPD policies table ───────────────────────────────────────────
        "CREATE TABLE IF NOT EXISTS lgpd_policies (id VARCHAR PRIMARY KEY, version VARCHAR(20) NOT NULL, title VARCHAR(300) NOT NULL DEFAULT 'Política de Privacidade e Proteção de Dados', intro_text TEXT, data_controller_text TEXT, data_collected_text TEXT, data_usage_text TEXT, data_retention_text TEXT, rights_text TEXT, contact_text TEXT, marketing_email_label VARCHAR(500) DEFAULT 'Desejo receber promoções e novidades por e-mail', marketing_whatsapp_label VARCHAR(500) DEFAULT 'Desejo receber promoções e novidades pelo WhatsApp', is_active BOOLEAN DEFAULT FALSE, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())",
        # ── Fix home_catalog_config show_promotions NULL rows ─────────────
        "UPDATE home_catalog_config SET show_promotions = TRUE WHERE show_promotions IS NULL",
        # ── Exit popup config ─────────────────────────────────────────────
        "CREATE TABLE IF NOT EXISTS exit_popup_config (id VARCHAR PRIMARY KEY DEFAULT 'default', enabled BOOLEAN DEFAULT FALSE, title VARCHAR(200) DEFAULT 'Espera! Temos uma oferta para você 🍕', subtitle TEXT DEFAULT 'Use o cupom abaixo e ganhe desconto no seu pedido!', coupon_code VARCHAR(50), button_text VARCHAR(100) DEFAULT 'Usar cupom agora', image_url TEXT, show_once_per_session BOOLEAN DEFAULT TRUE, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())",
        "INSERT INTO exit_popup_config (id) VALUES ('default') ON CONFLICT DO NOTHING",

        # ══════════════════════════════════════════════════════════════════════
        # MÓDULO MARKETING & CRM — Fase 1
        # ══════════════════════════════════════════════════════════════════════

        # ── Customer enhancements ─────────────────────────────────────────────
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS birth_date DATE",
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS tags TEXT DEFAULT '[]'",
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS crm_status VARCHAR(50) DEFAULT 'lead'",
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS source VARCHAR(100)",
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS notes TEXT",
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS first_order_at TIMESTAMPTZ",
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS last_order_at TIMESTAMPTZ",
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS total_orders INTEGER DEFAULT 0",
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS total_spent FLOAT DEFAULT 0.0",
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS avg_ticket FLOAT DEFAULT 0.0",

        # ── Customer groups ───────────────────────────────────────────────────
        "CREATE TABLE IF NOT EXISTS customer_groups (id VARCHAR PRIMARY KEY, name VARCHAR(200) NOT NULL, description TEXT, group_type VARCHAR(20) NOT NULL DEFAULT 'manual', color VARCHAR(20) DEFAULT '#f97316', icon VARCHAR(50), active BOOLEAN DEFAULT TRUE, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())",
        "CREATE TABLE IF NOT EXISTS customer_group_rules (id VARCHAR PRIMARY KEY, group_id VARCHAR NOT NULL REFERENCES customer_groups(id) ON DELETE CASCADE, field VARCHAR(100) NOT NULL, operator VARCHAR(30) NOT NULL, value TEXT NOT NULL, created_at TIMESTAMPTZ DEFAULT NOW())",
        "CREATE TABLE IF NOT EXISTS customer_group_members (id VARCHAR PRIMARY KEY, group_id VARCHAR NOT NULL REFERENCES customer_groups(id) ON DELETE CASCADE, customer_id VARCHAR NOT NULL REFERENCES customers(id) ON DELETE CASCADE, added_at TIMESTAMPTZ DEFAULT NOW(), CONSTRAINT uq_group_member UNIQUE(group_id, customer_id))",

        # ── Customer timeline / events ────────────────────────────────────────
        "CREATE TABLE IF NOT EXISTS customer_timeline (id VARCHAR PRIMARY KEY, customer_id VARCHAR NOT NULL REFERENCES customers(id) ON DELETE CASCADE, event_type VARCHAR(80) NOT NULL, title VARCHAR(300) NOT NULL, description TEXT, metadata_json TEXT, created_at TIMESTAMPTZ DEFAULT NOW())",
        "CREATE INDEX IF NOT EXISTS ix_customer_timeline_customer_id ON customer_timeline(customer_id)",
        "CREATE INDEX IF NOT EXISTS ix_customer_timeline_event_type ON customer_timeline(event_type)",
        "CREATE INDEX IF NOT EXISTS ix_customer_timeline_created_at ON customer_timeline(created_at DESC)",

        # ── CRM Pipelines ─────────────────────────────────────────────────────
        "CREATE TABLE IF NOT EXISTS crm_pipelines (id VARCHAR PRIMARY KEY, name VARCHAR(200) NOT NULL, description TEXT, pipeline_type VARCHAR(30) DEFAULT 'custom', active BOOLEAN DEFAULT TRUE, sort_order INTEGER DEFAULT 0, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())",
        "CREATE TABLE IF NOT EXISTS crm_stages (id VARCHAR PRIMARY KEY, pipeline_id VARCHAR NOT NULL REFERENCES crm_pipelines(id) ON DELETE CASCADE, name VARCHAR(200) NOT NULL, description TEXT, color VARCHAR(20) DEFAULT '#2d3d56', sort_order INTEGER DEFAULT 0, auto_move_rule TEXT, created_at TIMESTAMPTZ DEFAULT NOW())",
        "CREATE INDEX IF NOT EXISTS ix_crm_stages_pipeline_id ON crm_stages(pipeline_id)",
        "CREATE TABLE IF NOT EXISTS crm_cards (id VARCHAR PRIMARY KEY, pipeline_id VARCHAR NOT NULL REFERENCES crm_pipelines(id) ON DELETE CASCADE, stage_id VARCHAR NOT NULL REFERENCES crm_stages(id) ON DELETE CASCADE, customer_id VARCHAR REFERENCES customers(id) ON DELETE SET NULL, title VARCHAR(300) NOT NULL, description TEXT, value FLOAT, source VARCHAR(100), responsible VARCHAR(200), tags TEXT DEFAULT '[]', last_interaction_at TIMESTAMPTZ, next_follow_up_at TIMESTAMPTZ, sort_order INTEGER DEFAULT 0, archived BOOLEAN DEFAULT FALSE, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())",
        "CREATE INDEX IF NOT EXISTS ix_crm_cards_pipeline_id ON crm_cards(pipeline_id)",
        "CREATE INDEX IF NOT EXISTS ix_crm_cards_stage_id ON crm_cards(stage_id)",
        "CREATE INDEX IF NOT EXISTS ix_crm_cards_customer_id ON crm_cards(customer_id)",

        # ── CRM Tasks ─────────────────────────────────────────────────────────
        "CREATE TABLE IF NOT EXISTS crm_tasks (id VARCHAR PRIMARY KEY, card_id VARCHAR REFERENCES crm_cards(id) ON DELETE SET NULL, customer_id VARCHAR REFERENCES customers(id) ON DELETE SET NULL, title VARCHAR(300) NOT NULL, description TEXT, task_type VARCHAR(50) DEFAULT 'other', responsible VARCHAR(200), due_date TIMESTAMPTZ, priority VARCHAR(20) DEFAULT 'medium', status VARCHAR(20) DEFAULT 'pending', completed_at TIMESTAMPTZ, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())",
        "CREATE INDEX IF NOT EXISTS ix_crm_tasks_customer_id ON crm_tasks(customer_id)",
        "CREATE INDEX IF NOT EXISTS ix_crm_tasks_status ON crm_tasks(status)",
        # CRM card notes + history
        "CREATE TABLE IF NOT EXISTS crm_card_notes (id VARCHAR PRIMARY KEY, card_id VARCHAR NOT NULL REFERENCES crm_cards(id) ON DELETE CASCADE, author VARCHAR(200) DEFAULT 'Admin', body TEXT NOT NULL, created_at TIMESTAMPTZ DEFAULT NOW())",
        "CREATE INDEX IF NOT EXISTS ix_crm_card_notes_card_id ON crm_card_notes(card_id)",
        "CREATE TABLE IF NOT EXISTS crm_card_history (id VARCHAR PRIMARY KEY, card_id VARCHAR NOT NULL REFERENCES crm_cards(id) ON DELETE CASCADE, event_type VARCHAR(80) NOT NULL, description TEXT, created_at TIMESTAMPTZ DEFAULT NOW())",
        "CREATE INDEX IF NOT EXISTS ix_crm_card_history_card_id ON crm_card_history(card_id)",

        # ── Marketing Campaigns (unified) ─────────────────────────────────────
        "CREATE TABLE IF NOT EXISTS marketing_campaigns (id VARCHAR PRIMARY KEY, name VARCHAR(300) NOT NULL, campaign_type VARCHAR(50) NOT NULL, channel VARCHAR(50), status VARCHAR(30) DEFAULT 'draft', product_id VARCHAR REFERENCES products(id) ON DELETE SET NULL, coupon_id VARCHAR REFERENCES coupons(id) ON DELETE SET NULL, group_id VARCHAR REFERENCES customer_groups(id) ON DELETE SET NULL, budget FLOAT, spend FLOAT DEFAULT 0, revenue FLOAT DEFAULT 0, leads INTEGER DEFAULT 0, orders_count INTEGER DEFAULT 0, clicks INTEGER DEFAULT 0, impressions INTEGER DEFAULT 0, start_date DATE, end_date DATE, target_url TEXT, description TEXT, metadata_json TEXT, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())",
        "CREATE INDEX IF NOT EXISTS ix_marketing_campaigns_status ON marketing_campaigns(status)",
        "CREATE INDEX IF NOT EXISTS ix_marketing_campaigns_channel ON marketing_campaigns(channel)",

        # ── Visitor profiles & sessions ───────────────────────────────────────
        "CREATE TABLE IF NOT EXISTS visitor_profiles (id VARCHAR PRIMARY KEY, fingerprint VARCHAR(128) UNIQUE, customer_id VARCHAR REFERENCES customers(id) ON DELETE SET NULL, ip_hash VARCHAR(64), city VARCHAR(100), state VARCHAR(50), country VARCHAR(50), device_type VARCHAR(30), browser VARCHAR(80), os VARCHAR(80), first_seen_at TIMESTAMPTZ DEFAULT NOW(), last_seen_at TIMESTAMPTZ DEFAULT NOW(), total_sessions INTEGER DEFAULT 0, total_pageviews INTEGER DEFAULT 0, total_orders INTEGER DEFAULT 0)",
        "CREATE INDEX IF NOT EXISTS ix_visitor_profiles_fingerprint ON visitor_profiles(fingerprint)",
        "CREATE INDEX IF NOT EXISTS ix_visitor_profiles_customer_id ON visitor_profiles(customer_id)",
        "CREATE TABLE IF NOT EXISTS visitor_sessions (id VARCHAR PRIMARY KEY, visitor_id VARCHAR NOT NULL REFERENCES visitor_profiles(id) ON DELETE CASCADE, utm_source VARCHAR(100), utm_medium VARCHAR(100), utm_campaign VARCHAR(200), utm_content VARCHAR(200), utm_term VARCHAR(200), landing_page TEXT, referrer TEXT, started_at TIMESTAMPTZ DEFAULT NOW(), ended_at TIMESTAMPTZ, pageviews INTEGER DEFAULT 0)",
        "CREATE INDEX IF NOT EXISTS ix_visitor_sessions_visitor_id ON visitor_sessions(visitor_id)",
        "CREATE INDEX IF NOT EXISTS ix_visitor_sessions_started_at ON visitor_sessions(started_at DESC)",
        "CREATE TABLE IF NOT EXISTS visitor_events (id VARCHAR PRIMARY KEY, visitor_id VARCHAR NOT NULL REFERENCES visitor_profiles(id) ON DELETE CASCADE, session_id VARCHAR REFERENCES visitor_sessions(id) ON DELETE SET NULL, event_type VARCHAR(80) NOT NULL, page TEXT, product_id VARCHAR, metadata_json TEXT, created_at TIMESTAMPTZ DEFAULT NOW())",
        "CREATE INDEX IF NOT EXISTS ix_visitor_events_visitor_id ON visitor_events(visitor_id)",
        "CREATE INDEX IF NOT EXISTS ix_visitor_events_event_type ON visitor_events(event_type)",
        "CREATE INDEX IF NOT EXISTS ix_visitor_events_created_at ON visitor_events(created_at DESC)",

        # ── Tracking links ────────────────────────────────────────────────────
        "CREATE TABLE IF NOT EXISTS tracking_links (id VARCHAR PRIMARY KEY, slug VARCHAR(100) UNIQUE NOT NULL, destination_url TEXT NOT NULL, campaign_id VARCHAR REFERENCES marketing_campaigns(id) ON DELETE SET NULL, product_id VARCHAR REFERENCES products(id) ON DELETE SET NULL, coupon_id VARCHAR REFERENCES coupons(id) ON DELETE SET NULL, utm_source VARCHAR(100), utm_medium VARCHAR(100), utm_campaign VARCHAR(200), clicks INTEGER DEFAULT 0, unique_clicks INTEGER DEFAULT 0, orders_count INTEGER DEFAULT 0, revenue FLOAT DEFAULT 0, active BOOLEAN DEFAULT TRUE, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())",
        "CREATE INDEX IF NOT EXISTS ix_tracking_links_slug ON tracking_links(slug)",
        "CREATE TABLE IF NOT EXISTS tracking_clicks (id VARCHAR PRIMARY KEY, link_id VARCHAR NOT NULL REFERENCES tracking_links(id) ON DELETE CASCADE, visitor_id VARCHAR REFERENCES visitor_profiles(id) ON DELETE SET NULL, ip_hash VARCHAR(64), user_agent TEXT, referrer TEXT, created_at TIMESTAMPTZ DEFAULT NOW())",
        "CREATE INDEX IF NOT EXISTS ix_tracking_clicks_link_id ON tracking_clicks(link_id)",

        # ── Marketing settings ────────────────────────────────────────────────
        "CREATE TABLE IF NOT EXISTS marketing_settings (id VARCHAR PRIMARY KEY DEFAULT 'default', tracking_enabled BOOLEAN DEFAULT TRUE, ip_anonymization BOOLEAN DEFAULT TRUE, online_visitor_minutes INTEGER DEFAULT 5, data_retention_days INTEGER DEFAULT 365, attribution_window_days INTEGER DEFAULT 30, default_utm_source VARCHAR(100), default_utm_medium VARCHAR(100), tracking_domain VARCHAR(300), created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())",
        "INSERT INTO marketing_settings (id) VALUES ('default') ON CONFLICT DO NOTHING",

        # ── Integration credentials (encrypted at app level) ──────────────────
        "CREATE TABLE IF NOT EXISTS integration_connections (id VARCHAR PRIMARY KEY, integration_type VARCHAR(50) NOT NULL, status VARCHAR(20) DEFAULT 'disconnected', credentials_json TEXT, last_sync_at TIMESTAMPTZ, last_error TEXT, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW(), CONSTRAINT uq_integration_type UNIQUE(integration_type))",
        "INSERT INTO integration_connections (id, integration_type) VALUES ('meta_ads', 'meta_ads') ON CONFLICT DO NOTHING",
        "INSERT INTO integration_connections (id, integration_type) VALUES ('google_ads', 'google_ads') ON CONFLICT DO NOTHING",
        "INSERT INTO integration_connections (id, integration_type) VALUES ('tiktok_ads', 'tiktok_ads') ON CONFLICT DO NOTHING",
        "INSERT INTO integration_connections (id, integration_type) VALUES ('whatsapp_cloud', 'whatsapp_cloud') ON CONFLICT DO NOTHING",
        "INSERT INTO integration_connections (id, integration_type) VALUES ('whatsapp_qr', 'whatsapp_qr') ON CONFLICT DO NOTHING",
        "INSERT INTO integration_connections (id, integration_type) VALUES ('smtp', 'smtp') ON CONFLICT DO NOTHING",

        # ── Seed default CRM pipeline (Delivery) ──────────────────────────────
        "INSERT INTO crm_pipelines (id, name, description, pipeline_type, sort_order) VALUES ('delivery', 'Funil Delivery', 'Pipeline padrão para delivery', 'delivery', 0) ON CONFLICT DO NOTHING",
        "INSERT INTO crm_stages (id, pipeline_id, name, color, sort_order) VALUES ('st_novo', 'delivery', 'Novo cliente', '#6366f1', 0) ON CONFLICT DO NOTHING",
        "INSERT INTO crm_stages (id, pipeline_id, name, color, sort_order) VALUES ('st_visualizou', 'delivery', 'Visualizou produto', '#8b5cf6', 1) ON CONFLICT DO NOTHING",
        "INSERT INTO crm_stages (id, pipeline_id, name, color, sort_order) VALUES ('st_carrinho', 'delivery', 'Adicionou ao carrinho', '#f59e0b', 2) ON CONFLICT DO NOTHING",
        "INSERT INTO crm_stages (id, pipeline_id, name, color, sort_order) VALUES ('st_abandonou', 'delivery', 'Abandonou carrinho', '#ef4444', 3) ON CONFLICT DO NOTHING",
        "INSERT INTO crm_stages (id, pipeline_id, name, color, sort_order) VALUES ('st_primeiro', 'delivery', 'Primeiro pedido', '#10b981', 4) ON CONFLICT DO NOTHING",
        "INSERT INTO crm_stages (id, pipeline_id, name, color, sort_order) VALUES ('st_entregue', 'delivery', 'Pedido entregue', '#22c55e', 5) ON CONFLICT DO NOTHING",
        "INSERT INTO crm_stages (id, pipeline_id, name, color, sort_order) VALUES ('st_recorrente', 'delivery', 'Cliente recorrente', '#f97316', 6) ON CONFLICT DO NOTHING",
        "INSERT INTO crm_stages (id, pipeline_id, name, color, sort_order) VALUES ('st_inativo', 'delivery', 'Cliente inativo', '#94a3b8', 7) ON CONFLICT DO NOTHING",
        "INSERT INTO crm_stages (id, pipeline_id, name, color, sort_order) VALUES ('st_reativacao', 'delivery', 'Reativação', '#3b82f6', 8) ON CONFLICT DO NOTHING",

        # ══════════════════════════════════════════════════════════════════════
        # MÓDULO MARKETING — WhatsApp, Email & Automações
        # ══════════════════════════════════════════════════════════════════════

        # ── WhatsApp Marketing ────────────────────────────────────────────────
        "CREATE TABLE IF NOT EXISTS whatsapp_templates (id VARCHAR PRIMARY KEY, name VARCHAR(200) NOT NULL, body TEXT NOT NULL, category VARCHAR(50) DEFAULT 'marketing', language VARCHAR(10) DEFAULT 'pt_BR', active BOOLEAN DEFAULT TRUE, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())",
        "CREATE INDEX IF NOT EXISTS ix_whatsapp_templates_active ON whatsapp_templates(active)",
        "CREATE TABLE IF NOT EXISTS whatsapp_messages (id VARCHAR PRIMARY KEY, template_id VARCHAR REFERENCES whatsapp_templates(id) ON DELETE SET NULL, customer_id VARCHAR REFERENCES customers(id) ON DELETE SET NULL, phone VARCHAR(20) NOT NULL, body_sent TEXT, status VARCHAR(20) DEFAULT 'pending', wamid VARCHAR(200), error TEXT, sent_at TIMESTAMPTZ, created_at TIMESTAMPTZ DEFAULT NOW())",
        "CREATE INDEX IF NOT EXISTS ix_whatsapp_messages_customer_id ON whatsapp_messages(customer_id)",
        "CREATE INDEX IF NOT EXISTS ix_whatsapp_messages_status ON whatsapp_messages(status)",
        "CREATE INDEX IF NOT EXISTS ix_whatsapp_messages_created_at ON whatsapp_messages(created_at DESC)",
        # WhatsApp campaigns + config
        "CREATE TABLE IF NOT EXISTS whatsapp_campaigns (id VARCHAR PRIMARY KEY, name VARCHAR(300) NOT NULL, status VARCHAR(30) NOT NULL DEFAULT 'draft', template_id VARCHAR REFERENCES whatsapp_templates(id) ON DELETE SET NULL, group_id VARCHAR, scheduled_at TIMESTAMPTZ, sent_count INTEGER DEFAULT 0, delivered_count INTEGER DEFAULT 0, read_count INTEGER DEFAULT 0, error_count INTEGER DEFAULT 0, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())",
        "CREATE INDEX IF NOT EXISTS ix_whatsapp_campaigns_status ON whatsapp_campaigns(status)",
        "CREATE TABLE IF NOT EXISTS whatsapp_config (id VARCHAR PRIMARY KEY DEFAULT 'default', connection_type VARCHAR(30) DEFAULT 'official', status VARCHAR(20) DEFAULT 'disconnected', messages_per_minute INTEGER DEFAULT 10, interval_seconds INTEGER DEFAULT 3, daily_limit INTEGER DEFAULT 1000, webhook_url VARCHAR(500) DEFAULT '', updated_at TIMESTAMPTZ DEFAULT NOW())",
        "INSERT INTO whatsapp_config (id) VALUES ('default') ON CONFLICT DO NOTHING",
        "ALTER TABLE whatsapp_messages ADD COLUMN IF NOT EXISTS campaign_id VARCHAR REFERENCES whatsapp_campaigns(id) ON DELETE SET NULL",

        # ── Email Marketing ───────────────────────────────────────────────────
        "CREATE TABLE IF NOT EXISTS email_templates (id VARCHAR PRIMARY KEY, name VARCHAR(200) NOT NULL, subject VARCHAR(500) NOT NULL, body_html TEXT NOT NULL, active BOOLEAN DEFAULT TRUE, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())",
        "CREATE INDEX IF NOT EXISTS ix_email_templates_active ON email_templates(active)",
        "ALTER TABLE email_templates ADD COLUMN IF NOT EXISTS category VARCHAR(50) DEFAULT 'marketing'",
        "CREATE TABLE IF NOT EXISTS email_campaigns (id VARCHAR PRIMARY KEY, name VARCHAR(300) NOT NULL, status VARCHAR(30) NOT NULL DEFAULT 'draft', template_id VARCHAR REFERENCES email_templates(id) ON DELETE SET NULL, group_id VARCHAR, scheduled_at TIMESTAMPTZ, sent_count INTEGER DEFAULT 0, delivered_count INTEGER DEFAULT 0, open_count INTEGER DEFAULT 0, click_count INTEGER DEFAULT 0, bounce_count INTEGER DEFAULT 0, unsubscribe_count INTEGER DEFAULT 0, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())",
        "CREATE INDEX IF NOT EXISTS ix_email_campaigns_status ON email_campaigns(status)",
        "CREATE TABLE IF NOT EXISTS email_messages (id VARCHAR PRIMARY KEY, template_id VARCHAR REFERENCES email_templates(id) ON DELETE SET NULL, customer_id VARCHAR REFERENCES customers(id) ON DELETE SET NULL, to_email VARCHAR(300) NOT NULL, subject_sent VARCHAR(500), status VARCHAR(20) DEFAULT 'pending', error TEXT, sent_at TIMESTAMPTZ, created_at TIMESTAMPTZ DEFAULT NOW())",
        "ALTER TABLE email_messages ADD COLUMN IF NOT EXISTS campaign_id VARCHAR REFERENCES email_campaigns(id) ON DELETE SET NULL",
        "CREATE INDEX IF NOT EXISTS ix_email_messages_customer_id ON email_messages(customer_id)",
        "CREATE INDEX IF NOT EXISTS ix_email_messages_status ON email_messages(status)",
        "CREATE INDEX IF NOT EXISTS ix_email_messages_created_at ON email_messages(created_at DESC)",
        "CREATE TABLE IF NOT EXISTS email_config (id VARCHAR PRIMARY KEY DEFAULT 'default', provider VARCHAR(30) DEFAULT 'smtp', smtp_host VARCHAR(200) DEFAULT '', smtp_port INTEGER DEFAULT 587, smtp_user VARCHAR(300) DEFAULT '', smtp_password VARCHAR(500) DEFAULT '', from_name VARCHAR(200) DEFAULT 'Moschettieri', from_email VARCHAR(300) DEFAULT '', reply_to VARCHAR(300) DEFAULT '', status VARCHAR(20) DEFAULT 'disconnected', daily_limit INTEGER DEFAULT 5000, rate_per_hour INTEGER DEFAULT 500, updated_at TIMESTAMPTZ DEFAULT NOW())",
        "INSERT INTO email_config (id) VALUES ('default') ON CONFLICT DO NOTHING",

        # ── Marketing Automations ─────────────────────────────────────────────
        "CREATE TABLE IF NOT EXISTS marketing_automations (id VARCHAR PRIMARY KEY, name VARCHAR(200) NOT NULL, trigger VARCHAR(50) NOT NULL, trigger_value VARCHAR(100), channel VARCHAR(20) NOT NULL, template_id VARCHAR, message_body TEXT, active BOOLEAN DEFAULT TRUE, runs_total INTEGER DEFAULT 0, last_run_at TIMESTAMPTZ, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())",
        "CREATE INDEX IF NOT EXISTS ix_marketing_automations_trigger ON marketing_automations(trigger)",
        "CREATE INDEX IF NOT EXISTS ix_marketing_automations_active ON marketing_automations(active)",
        "CREATE TABLE IF NOT EXISTS automation_logs (id VARCHAR PRIMARY KEY, automation_id VARCHAR NOT NULL REFERENCES marketing_automations(id) ON DELETE CASCADE, customer_id VARCHAR REFERENCES customers(id) ON DELETE SET NULL, channel VARCHAR(20), status VARCHAR(20), error TEXT, created_at TIMESTAMPTZ DEFAULT NOW())",
        "CREATE INDEX IF NOT EXISTS ix_automation_logs_automation_id ON automation_logs(automation_id)",
        "CREATE INDEX IF NOT EXISTS ix_automation_logs_customer_id ON automation_logs(customer_id)",
        "CREATE INDEX IF NOT EXISTS ix_automation_logs_created_at ON automation_logs(created_at DESC)",
        # Automation templates + delay column
        "ALTER TABLE marketing_automations ADD COLUMN IF NOT EXISTS trigger_delay_hours INTEGER DEFAULT 0",
        "CREATE TABLE IF NOT EXISTS automation_templates (id VARCHAR PRIMARY KEY, name VARCHAR(200) NOT NULL, channel VARCHAR(20) NOT NULL DEFAULT 'whatsapp', subject VARCHAR(500), body TEXT NOT NULL, variables VARCHAR(500), category VARCHAR(50) DEFAULT 'marketing', created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())",
        "CREATE INDEX IF NOT EXISTS ix_automation_templates_channel ON automation_templates(channel)",

        # ══════════════════════════════════════════════════════════════════════
        # MÓDULO ADS — OAuth + CAPI + Campaign Sync — Fase 3
        # ══════════════════════════════════════════════════════════════════════
        "CREATE TABLE IF NOT EXISTS ads_oauth_states (id VARCHAR PRIMARY KEY, platform VARCHAR(30) NOT NULL, redirect_uri TEXT, created_at TIMESTAMPTZ DEFAULT NOW())",
        "CREATE TABLE IF NOT EXISTS ads_campaigns (id VARCHAR PRIMARY KEY, platform VARCHAR(30) NOT NULL, external_id VARCHAR(200) NOT NULL, name VARCHAR(300), status VARCHAR(30), objective VARCHAR(100), budget_daily FLOAT, spend FLOAT DEFAULT 0, impressions INTEGER DEFAULT 0, clicks INTEGER DEFAULT 0, conversions INTEGER DEFAULT 0, revenue FLOAT DEFAULT 0, ctr FLOAT DEFAULT 0, cpc FLOAT DEFAULT 0, cpa FLOAT DEFAULT 0, roas FLOAT DEFAULT 0, last_synced_at TIMESTAMPTZ, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())",
        "CREATE INDEX IF NOT EXISTS ix_ads_campaigns_platform ON ads_campaigns(platform)",
        "CREATE INDEX IF NOT EXISTS ix_ads_campaigns_spend ON ads_campaigns(spend DESC)",
        # Ads UTM links + pixels
        "CREATE TABLE IF NOT EXISTS ads_utm_links (id VARCHAR PRIMARY KEY, name VARCHAR(300) NOT NULL, url TEXT NOT NULL, utm_source VARCHAR(100) DEFAULT '', utm_medium VARCHAR(100) DEFAULT '', utm_campaign VARCHAR(200) DEFAULT '', utm_term VARCHAR(200) DEFAULT '', utm_content VARCHAR(200) DEFAULT '', clicks INTEGER DEFAULT 0, conversions INTEGER DEFAULT 0, created_at TIMESTAMPTZ DEFAULT NOW())",
        "CREATE TABLE IF NOT EXISTS ads_pixels (id VARCHAR PRIMARY KEY, platform VARCHAR(30) NOT NULL, pixel_id VARCHAR(200) NOT NULL, enabled BOOLEAN DEFAULT TRUE, events_tracked VARCHAR(500) DEFAULT 'PageView,Purchase,Lead', created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())",
        "CREATE INDEX IF NOT EXISTS ix_ads_pixels_platform ON ads_pixels(platform)",
        # UTM columns on customers (for lead attribution)
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS utm_source VARCHAR(100)",
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS utm_campaign VARCHAR(200)",

        # ══════════════════════════════════════════════════════════════════════
        # WORKFLOW DE APROVAÇÃO — Fase 4
        # ══════════════════════════════════════════════════════════════════════
        "CREATE TABLE IF NOT EXISTS marketing_workflows (id VARCHAR PRIMARY KEY, name VARCHAR(300) NOT NULL, campaign_type VARCHAR(50) NOT NULL DEFAULT 'whatsapp', status VARCHAR(40) NOT NULL DEFAULT 'draft', audience_description TEXT, template_preview TEXT, scheduled_at TIMESTAMPTZ, budget FLOAT, created_by VARCHAR(200) NOT NULL DEFAULT 'Admin', approved_by VARCHAR(200), approved_at TIMESTAMPTZ, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())",
        "CREATE INDEX IF NOT EXISTS ix_marketing_workflows_status ON marketing_workflows(status)",
        "CREATE TABLE IF NOT EXISTS marketing_workflow_comments (id VARCHAR PRIMARY KEY, workflow_id VARCHAR NOT NULL REFERENCES marketing_workflows(id) ON DELETE CASCADE, author VARCHAR(200) NOT NULL DEFAULT 'Admin', body TEXT NOT NULL, created_at TIMESTAMPTZ DEFAULT NOW())",
        "CREATE INDEX IF NOT EXISTS ix_marketing_workflow_comments_workflow_id ON marketing_workflow_comments(workflow_id)",

        # ══════════════════════════════════════════════════════════════════════
        # MÓDULO RBAC — Usuários, Perfis e Permissões
        # ══════════════════════════════════════════════════════════════════════
        "CREATE TABLE IF NOT EXISTS roles (id VARCHAR PRIMARY KEY, name VARCHAR(100) NOT NULL UNIQUE, description TEXT, is_system BOOLEAN DEFAULT FALSE, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())",
        "CREATE TABLE IF NOT EXISTS rbac_modules (id VARCHAR PRIMARY KEY, key VARCHAR(50) NOT NULL UNIQUE, name VARCHAR(100) NOT NULL, description TEXT, parent_id VARCHAR REFERENCES rbac_modules(id) ON DELETE SET NULL, order_index INTEGER DEFAULT 0, is_active BOOLEAN DEFAULT TRUE, created_at TIMESTAMPTZ DEFAULT NOW())",
        "CREATE TABLE IF NOT EXISTS rbac_permissions (id VARCHAR PRIMARY KEY, key VARCHAR(30) NOT NULL UNIQUE, name VARCHAR(100) NOT NULL, description TEXT)",
        "CREATE TABLE IF NOT EXISTS role_permissions (id VARCHAR PRIMARY KEY, role_id VARCHAR NOT NULL REFERENCES roles(id) ON DELETE CASCADE, module_id VARCHAR NOT NULL REFERENCES rbac_modules(id) ON DELETE CASCADE, permission_id VARCHAR NOT NULL REFERENCES rbac_permissions(id) ON DELETE CASCADE, allowed BOOLEAN DEFAULT TRUE, CONSTRAINT uq_role_module_perm UNIQUE (role_id, module_id, permission_id))",
        "CREATE TABLE IF NOT EXISTS user_permissions (id VARCHAR PRIMARY KEY, user_id VARCHAR NOT NULL REFERENCES admin_users(id) ON DELETE CASCADE, module_id VARCHAR NOT NULL REFERENCES rbac_modules(id) ON DELETE CASCADE, permission_id VARCHAR NOT NULL REFERENCES rbac_permissions(id) ON DELETE CASCADE, allowed BOOLEAN DEFAULT TRUE, overrides_role BOOLEAN DEFAULT TRUE, CONSTRAINT uq_user_module_perm UNIQUE (user_id, module_id, permission_id))",
        "CREATE TABLE IF NOT EXISTS admin_audit_logs (id VARCHAR PRIMARY KEY, user_id VARCHAR REFERENCES admin_users(id) ON DELETE SET NULL, user_name VARCHAR(200), action VARCHAR(50) NOT NULL, module_key VARCHAR(50), entity_type VARCHAR(100), entity_id VARCHAR(100), old_value TEXT, new_value TEXT, ip_address VARCHAR(50), user_agent TEXT, created_at TIMESTAMPTZ DEFAULT NOW())",
        "CREATE INDEX IF NOT EXISTS ix_role_permissions_role_id ON role_permissions(role_id)",
        "CREATE INDEX IF NOT EXISTS ix_user_permissions_user_id ON user_permissions(user_id)",
        "CREATE INDEX IF NOT EXISTS ix_admin_audit_logs_user_id ON admin_audit_logs(user_id)",
        "CREATE INDEX IF NOT EXISTS ix_admin_audit_logs_created_at ON admin_audit_logs(created_at DESC)",
        # Extend admin_users with RBAC fields
        "ALTER TABLE admin_users ADD COLUMN IF NOT EXISTS phone VARCHAR(30)",
        "ALTER TABLE admin_users ADD COLUMN IF NOT EXISTS role_id VARCHAR(100)",
        "ALTER TABLE admin_users ADD COLUMN IF NOT EXISTS store_id VARCHAR(100)",
        "ALTER TABLE admin_users ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ",
        "ALTER TABLE admin_users ADD COLUMN IF NOT EXISTS created_by VARCHAR",
        "ALTER TABLE admin_users ADD COLUMN IF NOT EXISTS updated_by VARCHAR",
        # ── Operational timer fields ──────────────────────────────────────────
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS paid_at TIMESTAMPTZ",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS preparation_started_at TIMESTAMPTZ",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS out_for_delivery_at TIMESTAMPTZ",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivered_at TIMESTAMPTZ",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS target_delivery_minutes INTEGER DEFAULT 45",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS total_time_minutes INTEGER",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS preparation_time_minutes INTEGER",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivery_time_minutes INTEGER",
        # ── Campaign card background color ────────────────────────────────────
        "ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS card_bg_color VARCHAR(20)",
        # ── Feature: Video banners ────────────────────────────────────────────
        "ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS media_type VARCHAR(10) DEFAULT 'image'",
        "ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS video_url TEXT",
        # ── Feature: Customer Events table ────────────────────────────────────
        "CREATE TABLE IF NOT EXISTS customer_events (id VARCHAR PRIMARY KEY, customer_id VARCHAR REFERENCES customers(id) ON DELETE SET NULL, session_id VARCHAR(200), event_type VARCHAR(80) NOT NULL, event_name VARCHAR(200), event_description TEXT, entity_type VARCHAR(80), entity_id VARCHAR, product_id VARCHAR REFERENCES products(id) ON DELETE SET NULL, order_id VARCHAR REFERENCES orders(id) ON DELETE SET NULL, campaign_id VARCHAR, coupon_id VARCHAR, metadata_json TEXT, source VARCHAR(100), utm_source VARCHAR(100), utm_medium VARCHAR(100), utm_campaign VARCHAR(200), device_type VARCHAR(30), browser VARCHAR(80), operating_system VARCHAR(80), ip_address VARCHAR(50), page_url TEXT, referrer_url TEXT, created_at TIMESTAMPTZ DEFAULT NOW())",
        "CREATE INDEX IF NOT EXISTS ix_customer_events_customer_id ON customer_events(customer_id)",
        "CREATE INDEX IF NOT EXISTS ix_customer_events_session_id ON customer_events(session_id)",
        "CREATE INDEX IF NOT EXISTS ix_customer_events_event_type ON customer_events(event_type)",
        "CREATE INDEX IF NOT EXISTS ix_customer_events_created_at ON customer_events(created_at DESC)",
        "CREATE INDEX IF NOT EXISTS ix_customer_events_order_id ON customer_events(order_id)",
        # ── Chatbot API keys stored in DB (survives restarts, no .env write needed) ──
        "ALTER TABLE chatbot_settings ADD COLUMN IF NOT EXISTS anthropic_api_key TEXT",
        "ALTER TABLE chatbot_settings ADD COLUMN IF NOT EXISTS openai_api_key TEXT",
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
app.include_router(paid_traffic_routes.router)
app.include_router(paid_traffic_routes.admin_router)
app.include_router(store_operation.router)
app.include_router(lgpd_routes.router)
app.include_router(lgpd_routes.admin_router)
app.include_router(exit_popup_routes.router)
app.include_router(admin_users_routes.router)
app.include_router(crm_routes.router)
app.include_router(marketing_routes.router)
app.include_router(marketing_routes.public_router)
app.include_router(whatsapp_marketing_routes.router)
app.include_router(email_marketing_routes.router)
app.include_router(automations_routes.router)
app.include_router(ads_oauth_routes.router)
app.include_router(marketing_workflow_routes.router)
app.include_router(rbac_routes.router)
app.include_router(customer_events_routes.router)

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
app.include_router(paid_traffic_routes.router, prefix="/api")
app.include_router(paid_traffic_routes.admin_router, prefix="/api")
app.include_router(store_operation.router, prefix="/api")
app.include_router(lgpd_routes.router, prefix="/api")
app.include_router(lgpd_routes.admin_router, prefix="/api")

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
