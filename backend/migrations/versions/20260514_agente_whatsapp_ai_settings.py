"""Add AGENTE WHATSAPP AI settings."""
from alembic import op


revision = "20260514_agente_whatsapp_ai_settings"
down_revision = "20260514_agente_whatsapp_internal_alerts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agente_whatsapp_ai_settings (
            id VARCHAR PRIMARY KEY DEFAULT 'default',
            enabled BOOLEAN NOT NULL DEFAULT TRUE,
            provider VARCHAR(40) NOT NULL DEFAULT 'internal',
            model VARCHAR(120) NOT NULL DEFAULT 'internal-rules-v1',
            temperature FLOAT NOT NULL DEFAULT 0.4,
            max_tokens INTEGER NOT NULL DEFAULT 800,
            prompt_base TEXT NOT NULL DEFAULT '',
            business_rules TEXT NOT NULL DEFAULT '',
            tone_of_voice TEXT NOT NULL DEFAULT '',
            objective TEXT NOT NULL DEFAULT '',
            transfer_instructions TEXT NOT NULL DEFAULT '',
            forbidden_topics TEXT NOT NULL DEFAULT '',
            allowed_tools_json TEXT NOT NULL DEFAULT '{}',
            openai_api_key TEXT,
            anthropic_api_key TEXT,
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        INSERT INTO agente_whatsapp_ai_settings (
            id, enabled, provider, model, temperature, max_tokens,
            prompt_base, business_rules, tone_of_voice, objective,
            transfer_instructions, forbidden_topics, allowed_tools_json, updated_at
        ) VALUES (
            'default',
            TRUE,
            'internal',
            'internal-rules-v1',
            0.4,
            800,
            'Voce e o AGENTE WHATSAPP oficial da loja. Atenda com objetividade, venda com naturalidade e use somente dados vindos das ferramentas reais.',
            'Nunca invente preco, promocao, status de pedido, frete, cupom ou forma de pagamento. Para criar pedido ou pagamento real, exija confirmacao explicita do cliente.',
            'Humano, cordial, direto e comercial, sem textos longos.',
            'Vender, atender, recuperar vendas e acompanhar pedidos pelo WhatsApp.',
            'Transferir para humano quando houver reclamacao grave, pagamento divergente ou pedido fora das regras.',
            'Nao prometer prazo, desconto, brinde ou disponibilidade sem ferramenta real.',
            '{"mode":"all_registered_tools"}',
            NOW()
        )
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS agente_whatsapp_ai_settings")
