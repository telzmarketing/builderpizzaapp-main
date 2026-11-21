"""Keep superseded order lines for post-production loss history."""

from alembic import op
import sqlalchemy as sa


revision = "20261121_post_production_amendment"
down_revision = "20261120_production_effects"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("order_items", sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_order_items_superseded_at", "order_items", ["superseded_at"])


def downgrade() -> None:
    # Removing this marker would make superseded lines visible again through
    # the canonical order-item relationship and could duplicate production.
    if not op.get_context().as_sql:
        has_history = op.get_bind().execute(sa.text(
            "SELECT EXISTS (SELECT 1 FROM order_items WHERE superseded_at IS NOT NULL)"
        )).scalar()
        if has_history:
            raise RuntimeError(
                "Refusing to downgrade post-production amendment markers because superseded history exists"
            )

    op.drop_index("ix_order_items_superseded_at", table_name="order_items")
    op.drop_column("order_items", "superseded_at")
