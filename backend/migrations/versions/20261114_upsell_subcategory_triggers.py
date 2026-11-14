"""Add canonical category and subcategory triggers to upsells."""

from alembic import op


revision = "20261114_upsell_subcategory_triggers"
down_revision = "20261114_product_landing_pages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE upsells ADD COLUMN IF NOT EXISTS "
        "trigger_category_id VARCHAR REFERENCES product_categories(id) ON DELETE SET NULL"
    )
    op.execute("ALTER TABLE upsells ADD COLUMN IF NOT EXISTS trigger_subcategory VARCHAR(100)")
    op.execute(
        "ALTER TABLE upsells ADD COLUMN IF NOT EXISTS "
        "trigger_subcategory_id VARCHAR REFERENCES product_categories(id) ON DELETE SET NULL"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_upsells_trigger_category_id ON upsells(trigger_category_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_upsells_trigger_subcategory_id ON upsells(trigger_subcategory_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_upsells_trigger_subcategory_id")
    op.execute("DROP INDEX IF EXISTS ix_upsells_trigger_category_id")
    op.execute("ALTER TABLE upsells DROP COLUMN IF EXISTS trigger_subcategory_id")
    op.execute("ALTER TABLE upsells DROP COLUMN IF EXISTS trigger_subcategory")
    op.execute("ALTER TABLE upsells DROP COLUMN IF EXISTS trigger_category_id")
