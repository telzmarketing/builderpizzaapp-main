"""Allow product landing pages independent from promotions."""

from alembic import op


revision = "20261114_product_landing_pages"
down_revision = "20261113_customer_reviews"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE promotion_landing_pages ADD COLUMN IF NOT EXISTS landing_type VARCHAR(20) NOT NULL DEFAULT 'promotion'")
    op.execute("ALTER TABLE promotion_landing_pages ALTER COLUMN promotion_id DROP NOT NULL")
    op.execute("UPDATE promotion_landing_pages SET landing_type = 'promotion' WHERE landing_type IS NULL")
    op.execute("ALTER TABLE promotion_landing_pages DROP CONSTRAINT IF EXISTS ck_promotion_landing_pages_landing_type")
    op.execute("ALTER TABLE promotion_landing_pages DROP CONSTRAINT IF EXISTS ck_promotion_landing_pages_type_promotion")
    op.execute("ALTER TABLE promotion_landing_pages ADD CONSTRAINT ck_promotion_landing_pages_landing_type CHECK (landing_type IN ('product', 'promotion'))")
    op.execute("ALTER TABLE promotion_landing_pages ADD CONSTRAINT ck_promotion_landing_pages_type_promotion CHECK ((landing_type = 'product' AND promotion_id IS NULL) OR (landing_type = 'promotion' AND promotion_id IS NOT NULL))")
    op.execute("CREATE INDEX IF NOT EXISTS ix_promotion_landing_pages_landing_type ON promotion_landing_pages (landing_type)")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_promotion_landing_pages_tenant_product_landing ON promotion_landing_pages (tenant_id, product_id) WHERE landing_type = 'product'")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_promotion_landing_pages_tenant_product_landing")
    op.execute("DROP INDEX IF EXISTS ix_promotion_landing_pages_landing_type")
    op.execute("ALTER TABLE promotion_landing_pages DROP CONSTRAINT IF EXISTS ck_promotion_landing_pages_type_promotion")
    op.execute("ALTER TABLE promotion_landing_pages DROP CONSTRAINT IF EXISTS ck_promotion_landing_pages_landing_type")
    op.execute("DO $$ BEGIN IF EXISTS (SELECT 1 FROM promotion_landing_pages WHERE landing_type = 'product') THEN RAISE EXCEPTION 'Cannot downgrade while product landing pages exist'; END IF; END $$")
    op.execute("ALTER TABLE promotion_landing_pages ALTER COLUMN promotion_id SET NOT NULL")
    op.execute("ALTER TABLE promotion_landing_pages DROP COLUMN IF EXISTS landing_type")
