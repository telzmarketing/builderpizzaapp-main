"""Add tenant/day purchase titles without changing invoice numbers."""

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from alembic import op
import sqlalchemy as sa


revision = "20261112_inventory_purchase_titles"
down_revision = "20261111_active_portion_config_uniqueness"
branch_labels = None
depends_on = None
BUSINESS_TIMEZONE = ZoneInfo("America/Sao_Paulo")


def upgrade() -> None:
    op.add_column("inventory_purchases", sa.Column("title", sa.String(length=32), nullable=True))
    op.add_column("inventory_purchases", sa.Column("purchase_date", sa.Date(), nullable=True))
    op.add_column("inventory_purchases", sa.Column("daily_sequence", sa.Integer(), nullable=True))

    bind = op.get_bind()
    purchases = sa.table(
        "inventory_purchases",
        sa.column("id", sa.String()),
        sa.column("tenant_id", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("title", sa.String()),
        sa.column("purchase_date", sa.Date()),
        sa.column("daily_sequence", sa.Integer()),
    )
    rows = bind.execute(
        sa.select(purchases.c.id, purchases.c.tenant_id, purchases.c.created_at)
        .order_by(purchases.c.tenant_id, purchases.c.created_at, purchases.c.id)
    ).mappings()
    counters: dict[tuple[str | None, date], int] = {}
    for row in rows:
        created_at = row["created_at"]
        if isinstance(created_at, datetime):
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            purchase_date = created_at.astimezone(BUSINESS_TIMEZONE).date()
        else:
            purchase_date = date.today()
        key = (row["tenant_id"], purchase_date)
        sequence = counters.get(key, 0) + 1
        counters[key] = sequence
        bind.execute(
            purchases.update().where(purchases.c.id == row["id"]).values(
                title=f"Compra {purchase_date:%d-%m-%Y}-{sequence:03d}",
                purchase_date=purchase_date,
                daily_sequence=sequence,
            )
        )

    op.alter_column("inventory_purchases", "title", nullable=False)
    op.alter_column("inventory_purchases", "purchase_date", nullable=False)
    op.alter_column("inventory_purchases", "daily_sequence", nullable=False)
    op.create_index(
        "uq_inventory_purchases_tenant_date_sequence",
        "inventory_purchases",
        ["tenant_id", "purchase_date", "daily_sequence"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_inventory_purchases_tenant_date_sequence", table_name="inventory_purchases")
    op.drop_column("inventory_purchases", "daily_sequence")
    op.drop_column("inventory_purchases", "purchase_date")
    op.drop_column("inventory_purchases", "title")
