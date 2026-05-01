"""runtime schema backfill core

Revision ID: 20260426_runtime_schema_backfill_core
Revises: 20260425_loyalty_settings
Create Date: 2026-04-26
"""
from __future__ import annotations

from alembic import op

revision = "20260426_runtime_schema_backfill_core"
down_revision = "20260425_loyalty_settings"
branch_labels = None
depends_on = None


DDL = [
    # Chatbot schema currently bootstrapped by backend.main._run_migrations.
    "CREATE TABLE IF NOT EXISTS chatbot_settings (id VARCHAR PRIMARY KEY DEFAULT 'default', ativo BOOLEAN DEFAULT TRUE, nome_bot VARCHAR(100) DEFAULT 'Assistente', mensagem_inicial TEXT DEFAULT 'Ola! Como posso ajudar?', cor_primaria VARCHAR(20) DEFAULT '#f97316', posicao_widget VARCHAR(20) DEFAULT 'bottom-right', horario_funcionamento TEXT, mensagem_fora_horario TEXT DEFAULT 'Estamos fora do horario de atendimento.', tempo_disparo_auto INTEGER DEFAULT 0, fallback_humano_ativo BOOLEAN DEFAULT TRUE, provedor_ia VARCHAR(20) DEFAULT 'claude', modelo_ia VARCHAR(100) DEFAULT 'claude-sonnet-4-20250514', temperatura FLOAT DEFAULT 0.7, max_tokens INTEGER DEFAULT 1024, prompt_base TEXT DEFAULT '', regras_fixas TEXT DEFAULT '', tom_de_voz TEXT DEFAULT '', objetivo TEXT DEFAULT '', instrucoes_transferencia TEXT DEFAULT '', limitacoes_proibicoes TEXT DEFAULT '', updated_at TIMESTAMPTZ DEFAULT NOW())",
    "INSERT INTO chatbot_settings (id) VALUES ('default') ON CONFLICT DO NOTHING",
    "CREATE TABLE IF NOT EXISTS chatbot_faq (id VARCHAR PRIMARY KEY, pergunta TEXT NOT NULL, resposta TEXT NOT NULL, categoria VARCHAR(100) DEFAULT 'geral', prioridade INTEGER DEFAULT 0, ativo BOOLEAN DEFAULT TRUE, vinculo_produto_id VARCHAR REFERENCES products(id) ON DELETE SET NULL, busca_vetor TSVECTOR, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())",
    "CREATE INDEX IF NOT EXISTS ix_chatbot_faq_busca_vetor ON chatbot_faq USING gin (busca_vetor) WHERE busca_vetor IS NOT NULL",
    "CREATE TABLE IF NOT EXISTS chatbot_conversations (id VARCHAR PRIMARY KEY, session_id VARCHAR UNIQUE NOT NULL, cliente_id VARCHAR REFERENCES customers(id) ON DELETE SET NULL, visitor_fingerprint VARCHAR(100), pagina_origem VARCHAR(500), user_agent TEXT, ip_hash VARCHAR(64), status VARCHAR(20) DEFAULT 'aberta', tags TEXT, iniciada_em TIMESTAMPTZ DEFAULT NOW(), encerrada_em TIMESTAMPTZ, assumida_por_user_id VARCHAR REFERENCES admin_users(id) ON DELETE SET NULL, intencao_detectada VARCHAR(200), resumo_conversa TEXT)",
    "CREATE INDEX IF NOT EXISTS ix_chatbot_conversations_session_id ON chatbot_conversations(session_id)",
    "CREATE INDEX IF NOT EXISTS ix_chatbot_conv_status_iniciada ON chatbot_conversations(status, iniciada_em)",
    "CREATE TABLE IF NOT EXISTS chatbot_messages (id VARCHAR PRIMARY KEY, conversation_id VARCHAR NOT NULL REFERENCES chatbot_conversations(id) ON DELETE CASCADE, sender VARCHAR(20) NOT NULL, mensagem TEXT NOT NULL, tipo VARCHAR(20) DEFAULT 'text', tokens_consumidos INTEGER, provedor_usado VARCHAR(50), latencia_ms INTEGER, contexto_usado TEXT, timestamp TIMESTAMPTZ DEFAULT NOW())",
    "CREATE INDEX IF NOT EXISTS ix_chatbot_messages_conversation_id ON chatbot_messages(conversation_id)",
    "CREATE INDEX IF NOT EXISTS ix_chatbot_messages_timestamp ON chatbot_messages(timestamp)",
    "CREATE TABLE IF NOT EXISTS chatbot_handoffs (id VARCHAR PRIMARY KEY, conversation_id VARCHAR NOT NULL REFERENCES chatbot_conversations(id) ON DELETE CASCADE, operador_id VARCHAR REFERENCES admin_users(id) ON DELETE SET NULL, motivo VARCHAR(500), assumido_em TIMESTAMPTZ DEFAULT NOW(), encerrado_em TIMESTAMPTZ)",
    "CREATE INDEX IF NOT EXISTS ix_chatbot_handoffs_conversation_id ON chatbot_handoffs(conversation_id)",
    "CREATE TABLE IF NOT EXISTS chatbot_knowledge_docs (id VARCHAR PRIMARY KEY, titulo VARCHAR(300) NOT NULL, conteudo TEXT NOT NULL, tipo VARCHAR(50) DEFAULT 'geral', ativo BOOLEAN DEFAULT TRUE, busca_vetor TSVECTOR, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())",
    "CREATE INDEX IF NOT EXISTS ix_chatbot_kdoc_busca_vetor ON chatbot_knowledge_docs USING gin (busca_vetor) WHERE busca_vetor IS NOT NULL",
    "CREATE TABLE IF NOT EXISTS chatbot_automations (id VARCHAR PRIMARY KEY, nome VARCHAR(200) NOT NULL, gatilho VARCHAR(50) NOT NULL, condicao TEXT DEFAULT '{}', mensagem TEXT NOT NULL, ativo BOOLEAN DEFAULT TRUE, prioridade INTEGER DEFAULT 0, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())",
    "ALTER TABLE IF EXISTS chatbot_automations ADD COLUMN IF NOT EXISTS condicao TEXT DEFAULT '{}'",
    "ALTER TABLE IF EXISTS chatbot_automations ADD COLUMN IF NOT EXISTS prioridade INTEGER DEFAULT 0",
    "ALTER TABLE IF EXISTS chatbot_automations ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()",
    "ALTER TABLE IF EXISTS chatbot_messages ADD COLUMN IF NOT EXISTS contexto_usado TEXT",
    "ALTER TABLE IF EXISTS chatbot_handoffs ADD COLUMN IF NOT EXISTS operador_id VARCHAR REFERENCES admin_users(id) ON DELETE SET NULL",
    "ALTER TABLE IF EXISTS chatbot_knowledge_docs ADD COLUMN IF NOT EXISTS busca_vetor TSVECTOR",
    # Visual/storefront singleton tables.
    "CREATE TABLE IF NOT EXISTS theme_settings (id VARCHAR PRIMARY KEY DEFAULT 'default', \"primary\" VARCHAR(20) NOT NULL DEFAULT '#f97316', secondary VARCHAR(20) NOT NULL DEFAULT '#2d3d56', background_main VARCHAR(20) NOT NULL DEFAULT '#0c1220', background_alt VARCHAR(20) NOT NULL DEFAULT '#111827', background_card VARCHAR(20) NOT NULL DEFAULT '#1e2a3b', text_primary VARCHAR(20) NOT NULL DEFAULT '#f8fafc', text_secondary VARCHAR(20) NOT NULL DEFAULT '#e2e8f0', text_muted VARCHAR(20) NOT NULL DEFAULT '#94a3b8', status_success VARCHAR(20) NOT NULL DEFAULT '#22c55e', status_error VARCHAR(20) NOT NULL DEFAULT '#ef4444', status_warning VARCHAR(20) NOT NULL DEFAULT '#f59e0b', status_info VARCHAR(20) NOT NULL DEFAULT '#3b82f6', border VARCHAR(20) NOT NULL DEFAULT '#2d3d56', interaction_hover VARCHAR(20) NOT NULL DEFAULT '#fb923c', interaction_active VARCHAR(20) NOT NULL DEFAULT '#ea6f10', interaction_focus VARCHAR(20) NOT NULL DEFAULT '#f97316', navbar VARCHAR(20) NOT NULL DEFAULT '#111827', footer VARCHAR(20) NOT NULL DEFAULT '#0c1220', sidebar VARCHAR(20) NOT NULL DEFAULT '#111827', modal VARCHAR(20) NOT NULL DEFAULT '#1e2a3b', overlay VARCHAR(20) NOT NULL DEFAULT '#000000', badge VARCHAR(20) NOT NULL DEFAULT '#f97316', tag VARCHAR(20) NOT NULL DEFAULT '#2d3d56', home_banner_background VARCHAR(20) NOT NULL DEFAULT '#1f2937', created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())",
    "INSERT INTO theme_settings (id) VALUES ('default') ON CONFLICT DO NOTHING",
    "ALTER TABLE IF EXISTS theme_settings ADD COLUMN IF NOT EXISTS home_banner_background VARCHAR(20) NOT NULL DEFAULT '#1f2937'",
    "CREATE TABLE IF NOT EXISTS home_catalog_config (id VARCHAR PRIMARY KEY DEFAULT 'default', mode VARCHAR(20) NOT NULL DEFAULT 'all', selected_categories TEXT DEFAULT '[]', selected_product_ids TEXT DEFAULT '[]', show_promotions BOOLEAN DEFAULT TRUE, updated_at TIMESTAMPTZ DEFAULT NOW())",
    "INSERT INTO home_catalog_config (id) VALUES ('default') ON CONFLICT DO NOTHING",
    "CREATE TABLE IF NOT EXISTS lgpd_policies (id VARCHAR PRIMARY KEY, version VARCHAR(20) NOT NULL, title VARCHAR(300) NOT NULL DEFAULT 'Politica de Privacidade e Protecao de Dados', intro_text TEXT, data_controller_text TEXT, data_collected_text TEXT, data_usage_text TEXT, data_retention_text TEXT, rights_text TEXT, contact_text TEXT, marketing_email_label VARCHAR(500), marketing_whatsapp_label VARCHAR(500), is_active BOOLEAN DEFAULT FALSE, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())",
    "CREATE TABLE IF NOT EXISTS exit_popup_config (id VARCHAR PRIMARY KEY DEFAULT 'default', enabled BOOLEAN DEFAULT FALSE, title VARCHAR(200) DEFAULT 'Espera! Temos uma oferta para voce', subtitle TEXT DEFAULT 'Use o cupom abaixo e ganhe desconto no seu pedido!', coupon_code VARCHAR(50), button_text VARCHAR(100) DEFAULT 'Usar cupom agora', image_url TEXT, show_once_per_session BOOLEAN DEFAULT TRUE, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())",
    "INSERT INTO exit_popup_config (id) VALUES ('default') ON CONFLICT DO NOTHING",
    "ALTER TABLE IF EXISTS exit_popup_config ADD COLUMN IF NOT EXISTS subtitle TEXT DEFAULT 'Use o cupom abaixo e ganhe desconto no seu pedido!'",
    "ALTER TABLE IF EXISTS exit_popup_config ADD COLUMN IF NOT EXISTS button_text VARCHAR(100) DEFAULT 'Usar cupom agora'",
    "ALTER TABLE IF EXISTS exit_popup_config ADD COLUMN IF NOT EXISTS show_once_per_session BOOLEAN DEFAULT TRUE",
    "ALTER TABLE IF EXISTS exit_popup_config ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()",
    # Customer/account fields used by LGPD, CRM and attribution flows.
    "ALTER TABLE IF EXISTS customers ADD COLUMN IF NOT EXISTS google_id VARCHAR(200)",
    "ALTER TABLE IF EXISTS customers ADD COLUMN IF NOT EXISTS lgpd_consent BOOLEAN DEFAULT FALSE",
    "ALTER TABLE IF EXISTS customers ADD COLUMN IF NOT EXISTS lgpd_consent_at TIMESTAMPTZ",
    "ALTER TABLE IF EXISTS customers ADD COLUMN IF NOT EXISTS lgpd_policy_version VARCHAR(20)",
    "ALTER TABLE IF EXISTS customers ADD COLUMN IF NOT EXISTS marketing_email_consent BOOLEAN DEFAULT FALSE",
    "ALTER TABLE IF EXISTS customers ADD COLUMN IF NOT EXISTS marketing_whatsapp_consent BOOLEAN DEFAULT FALSE",
    "ALTER TABLE IF EXISTS customers ADD COLUMN IF NOT EXISTS crm_status VARCHAR(40) DEFAULT 'lead'",
    "ALTER TABLE IF EXISTS customers ADD COLUMN IF NOT EXISTS lead_source VARCHAR(100)",
    "ALTER TABLE IF EXISTS customers ADD COLUMN IF NOT EXISTS notes TEXT",
    "ALTER TABLE IF EXISTS customers ADD COLUMN IF NOT EXISTS tags TEXT DEFAULT '[]'",
    "ALTER TABLE IF EXISTS customers ADD COLUMN IF NOT EXISTS last_contact_at TIMESTAMPTZ",
    "ALTER TABLE IF EXISTS customers ADD COLUMN IF NOT EXISTS utm_source VARCHAR(100)",
    "ALTER TABLE IF EXISTS customers ADD COLUMN IF NOT EXISTS utm_campaign VARCHAR(200)",
    "CREATE UNIQUE INDEX IF NOT EXISTS ix_customers_google_id_unique ON customers(google_id) WHERE google_id IS NOT NULL",
    "ALTER TABLE IF EXISTS addresses ADD COLUMN IF NOT EXISTS label VARCHAR(100)",
    # RBAC and admin audit schema.
    "CREATE TABLE IF NOT EXISTS roles (id VARCHAR PRIMARY KEY, name VARCHAR(100) NOT NULL UNIQUE, description TEXT, is_system BOOLEAN DEFAULT FALSE, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())",
    "CREATE TABLE IF NOT EXISTS rbac_modules (id VARCHAR PRIMARY KEY, key VARCHAR(50) NOT NULL UNIQUE, name VARCHAR(100) NOT NULL, description TEXT, parent_id VARCHAR REFERENCES rbac_modules(id) ON DELETE SET NULL, order_index INTEGER DEFAULT 0, is_active BOOLEAN DEFAULT TRUE, created_at TIMESTAMPTZ DEFAULT NOW())",
    "CREATE TABLE IF NOT EXISTS rbac_permissions (id VARCHAR PRIMARY KEY, key VARCHAR(30) NOT NULL UNIQUE, name VARCHAR(100) NOT NULL, description TEXT)",
    "CREATE TABLE IF NOT EXISTS role_permissions (id VARCHAR PRIMARY KEY, role_id VARCHAR NOT NULL REFERENCES roles(id) ON DELETE CASCADE, module_id VARCHAR NOT NULL REFERENCES rbac_modules(id) ON DELETE CASCADE, permission_id VARCHAR NOT NULL REFERENCES rbac_permissions(id) ON DELETE CASCADE, allowed BOOLEAN DEFAULT TRUE)",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_role_module_perm ON role_permissions(role_id, module_id, permission_id)",
    "CREATE INDEX IF NOT EXISTS ix_role_permissions_role_id ON role_permissions(role_id)",
    "CREATE TABLE IF NOT EXISTS user_permissions (id VARCHAR PRIMARY KEY, user_id VARCHAR NOT NULL REFERENCES admin_users(id) ON DELETE CASCADE, module_id VARCHAR NOT NULL REFERENCES rbac_modules(id) ON DELETE CASCADE, permission_id VARCHAR NOT NULL REFERENCES rbac_permissions(id) ON DELETE CASCADE, allowed BOOLEAN DEFAULT TRUE, overrides_role BOOLEAN DEFAULT TRUE)",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_user_module_perm ON user_permissions(user_id, module_id, permission_id)",
    "CREATE INDEX IF NOT EXISTS ix_user_permissions_user_id ON user_permissions(user_id)",
    "CREATE TABLE IF NOT EXISTS admin_audit_logs (id VARCHAR PRIMARY KEY, user_id VARCHAR REFERENCES admin_users(id) ON DELETE SET NULL, user_name VARCHAR(200), action VARCHAR(50) NOT NULL, module_key VARCHAR(50), entity_type VARCHAR(100), entity_id VARCHAR(100), old_value TEXT, new_value TEXT, ip_address VARCHAR(50), user_agent TEXT, created_at TIMESTAMPTZ DEFAULT NOW())",
    "CREATE INDEX IF NOT EXISTS ix_admin_audit_logs_user_id ON admin_audit_logs(user_id)",
    "CREATE INDEX IF NOT EXISTS ix_admin_audit_logs_created_at ON admin_audit_logs(created_at DESC)",
    "ALTER TABLE IF EXISTS admin_users ADD COLUMN IF NOT EXISTS phone VARCHAR(30)",
    "ALTER TABLE IF EXISTS admin_users ADD COLUMN IF NOT EXISTS role_id VARCHAR(100)",
    "ALTER TABLE IF EXISTS admin_users ADD COLUMN IF NOT EXISTS store_id VARCHAR(100)",
    "ALTER TABLE IF EXISTS admin_users ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ",
    "ALTER TABLE IF EXISTS admin_users ADD COLUMN IF NOT EXISTS created_by VARCHAR",
    "ALTER TABLE IF EXISTS admin_users ADD COLUMN IF NOT EXISTS updated_by VARCHAR",
    # Operational order and campaign fields consumed by current services/UI.
    "ALTER TABLE IF EXISTS orders ADD COLUMN IF NOT EXISTS paid_at TIMESTAMPTZ",
    "ALTER TABLE IF EXISTS orders ADD COLUMN IF NOT EXISTS preparation_started_at TIMESTAMPTZ",
    "ALTER TABLE IF EXISTS orders ADD COLUMN IF NOT EXISTS out_for_delivery_at TIMESTAMPTZ",
    "ALTER TABLE IF EXISTS orders ADD COLUMN IF NOT EXISTS delivered_at TIMESTAMPTZ",
    "ALTER TABLE IF EXISTS orders ADD COLUMN IF NOT EXISTS target_delivery_minutes INTEGER DEFAULT 45",
    "ALTER TABLE IF EXISTS orders ADD COLUMN IF NOT EXISTS total_time_minutes INTEGER",
    "ALTER TABLE IF EXISTS orders ADD COLUMN IF NOT EXISTS preparation_time_minutes INTEGER",
    "ALTER TABLE IF EXISTS orders ADD COLUMN IF NOT EXISTS delivery_time_minutes INTEGER",
    "ALTER TABLE IF EXISTS campaigns ADD COLUMN IF NOT EXISTS active_days VARCHAR(20)",
    "ALTER TABLE IF EXISTS campaigns ADD COLUMN IF NOT EXISTS card_bg_color VARCHAR(20)",
    "ALTER TABLE IF EXISTS campaigns ADD COLUMN IF NOT EXISTS media_type VARCHAR(10) DEFAULT 'image'",
    "ALTER TABLE IF EXISTS campaigns ADD COLUMN IF NOT EXISTS video_url TEXT",
    # Customer event tracking model.
    "CREATE TABLE IF NOT EXISTS customer_events (id VARCHAR PRIMARY KEY, customer_id VARCHAR REFERENCES customers(id) ON DELETE SET NULL, session_id VARCHAR(200), event_type VARCHAR(80) NOT NULL, event_name VARCHAR(200), event_description TEXT, entity_type VARCHAR(80), entity_id VARCHAR, product_id VARCHAR REFERENCES products(id) ON DELETE SET NULL, order_id VARCHAR REFERENCES orders(id) ON DELETE SET NULL, campaign_id VARCHAR, coupon_id VARCHAR, metadata_json TEXT, source VARCHAR(100), utm_source VARCHAR(100), utm_medium VARCHAR(100), utm_campaign VARCHAR(200), device_type VARCHAR(30), browser VARCHAR(80), operating_system VARCHAR(80), ip_address VARCHAR(50), page_url TEXT, referrer_url TEXT, created_at TIMESTAMPTZ DEFAULT NOW())",
    "CREATE INDEX IF NOT EXISTS ix_customer_events_customer_id ON customer_events(customer_id)",
    "CREATE INDEX IF NOT EXISTS ix_customer_events_session_id ON customer_events(session_id)",
    "CREATE INDEX IF NOT EXISTS ix_customer_events_event_type ON customer_events(event_type)",
    "CREATE INDEX IF NOT EXISTS ix_customer_events_created_at ON customer_events(created_at DESC)",
    "CREATE INDEX IF NOT EXISTS ix_customer_events_order_id ON customer_events(order_id)",
]


def upgrade() -> None:
    for statement in DDL:
        op.execute(statement)


def downgrade() -> None:
    # This migration documents runtime-created production schema in Alembic.
    # Dropping these objects automatically would risk data loss.
    pass
