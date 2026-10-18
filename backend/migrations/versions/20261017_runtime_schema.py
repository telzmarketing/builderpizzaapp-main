"""Restore five marketing columns omitted from the versioned runtime schema.

Keep the established model/startup-bootstrap contract. These additive columns
do not change tenant ownership, JSON representation or existing configuration.
"""
from alembic import op


revision = "20261017_runtime_schema"
down_revision = "20261017_delivery_schema"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE email_templates ADD COLUMN IF NOT EXISTS "
        "category VARCHAR(50) DEFAULT 'marketing'"
    )
    op.execute(
        "ALTER TABLE marketing_automations ADD COLUMN IF NOT EXISTS "
        "trigger_delay_hours INTEGER DEFAULT 0"
    )
    for definition in (
        "active_weekdays VARCHAR(20)",
        "pixel_id VARCHAR",
        "pixel_events VARCHAR(500)",
    ):
        op.execute(f"ALTER TABLE traffic_campaigns ADD COLUMN IF NOT EXISTS {definition}")


def downgrade():
    raise RuntimeError(
        "Runtime schema is forward-only; existing marketing configuration must be preserved."
    )
