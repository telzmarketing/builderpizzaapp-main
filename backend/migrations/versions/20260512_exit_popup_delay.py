"""Add timed trigger to exit popup."""

from alembic import op


revision = "20260512_exit_popup_delay"
down_revision = "20260512_delivery_problem_resolution"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE exit_popup_config ADD COLUMN IF NOT EXISTS trigger_delay_seconds INTEGER DEFAULT 10")


def downgrade() -> None:
    op.execute("ALTER TABLE exit_popup_config DROP COLUMN IF EXISTS trigger_delay_seconds")
