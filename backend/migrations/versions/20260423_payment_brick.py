"""payment brick tables and columns

Revision ID: 20260423_payment_brick
Revises: None
Create Date: 2026-04-23
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

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

    op.add_column("orders", sa.Column("external_reference", sa.String(length=120), nullable=True))
    op.create_index("ix_orders_external_reference", "orders", ["external_reference"], unique=True, postgresql_where=sa.text("external_reference IS NOT NULL"))
    op.add_column("payments", sa.Column("provider", sa.String(length=50), nullable=True, server_default="mock"))
    op.add_column("payments", sa.Column("mercado_pago_payment_id", sa.String(length=100), nullable=True))
    op.create_index("ix_payments_mercado_pago_payment_id", "payments", ["mercado_pago_payment_id"], unique=True, postgresql_where=sa.text("mercado_pago_payment_id IS NOT NULL"))
    op.add_column("payments", sa.Column("external_reference", sa.String(length=120), nullable=True))
    op.add_column("payments", sa.Column("raw_response", sa.Text(), nullable=True))
    op.add_column("payments", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "payment_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False, server_default="mercado_pago"),
        sa.Column("event_type", sa.String(length=100), nullable=True),
        sa.Column("mercado_pago_payment_id", sa.String(length=100), nullable=True),
        sa.Column("external_reference", sa.String(length=120), nullable=True),
        sa.Column("raw_payload", sa.Text(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
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
