"""payment brick tables and columns

Revision ID: 20260423_payment_brick
Revises: None
Create Date: 2026-04-23
"""
from __future__ import annotations

from alembic import op

revision = "20260423_payment_brick"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    for value in ("aguardando_pagamento", "pago", "pagamento_recusado", "pagamento_expirado", "ready_for_pickup"):
        op.execute(f"ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS '{value}'")
    for value in ("approved", "rejected", "cancelled", "expired"):
        op.execute(f"ALTER TYPE paymentstatus ADD VALUE IF NOT EXISTS '{value}'")
    op.execute("ALTER TYPE paymentmethod ADD VALUE IF NOT EXISTS 'debit_card'")

    op.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS external_reference VARCHAR(120)")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_orders_external_reference "
        "ON orders(external_reference) WHERE external_reference IS NOT NULL"
    )
    op.execute("ALTER TABLE payments ADD COLUMN IF NOT EXISTS provider VARCHAR(50) DEFAULT 'mock'")
    op.execute("ALTER TABLE payments ADD COLUMN IF NOT EXISTS mercado_pago_payment_id VARCHAR(100)")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_payments_mercado_pago_payment_id "
        "ON payments(mercado_pago_payment_id) WHERE mercado_pago_payment_id IS NOT NULL"
    )
    op.execute("ALTER TABLE payments ADD COLUMN IF NOT EXISTS external_reference VARCHAR(120)")
    op.execute("ALTER TABLE payments ADD COLUMN IF NOT EXISTS raw_response TEXT")
    op.execute("ALTER TABLE payments ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS payment_events (
            id VARCHAR PRIMARY KEY,
            provider VARCHAR(50) NOT NULL DEFAULT 'mercado_pago',
            event_type VARCHAR(100),
            mercado_pago_payment_id VARCHAR(100),
            external_reference VARCHAR(120),
            raw_payload TEXT NOT NULL,
            processed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ
        )
        """
    )


def downgrade() -> None:
    op.drop_table("payment_events")
    op.drop_column("payments", "updated_at")
    op.drop_column("payments", "raw_response")
    op.drop_column("payments", "external_reference")
    op.drop_index("ix_payments_mercado_pago_payment_id", table_name="payments")
    op.drop_column("payments", "mercado_pago_payment_id")
    op.drop_column("payments", "provider")
    op.drop_index("ix_orders_external_reference", table_name="orders")
    op.drop_column("orders", "external_reference")
