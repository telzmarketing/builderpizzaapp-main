"""Add delivery problem resolution fields."""

from alembic import op


revision = "20260512_delivery_problem_resolution"
down_revision = "20260511_best_seller_badge"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE deliveries ADD COLUMN IF NOT EXISTS problem_resolved_at TIMESTAMPTZ")
    op.execute("ALTER TABLE deliveries ADD COLUMN IF NOT EXISTS admin_resolution_note TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE deliveries DROP COLUMN IF EXISTS admin_resolution_note")
    op.execute("ALTER TABLE deliveries DROP COLUMN IF EXISTS problem_resolved_at")
