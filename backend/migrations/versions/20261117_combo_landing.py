"""Add public combo landing fields."""

from alembic import op
import sqlalchemy as sa

revision = "20261117_combo_landing"
down_revision = "20261117_production_vision_devices"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("promotional_kits", sa.Column("slug", sa.String(200), nullable=True))
    op.add_column("promotional_kits", sa.Column("image_url", sa.Text(), nullable=True))
    op.add_column("promotional_kits", sa.Column("video_url", sa.Text(), nullable=True))
    op.create_index("ix_promotional_kits_slug", "promotional_kits", ["slug"])
    op.execute("UPDATE promotional_kits SET slug = 'combo-' || substr(id, 1, 12) WHERE slug IS NULL")


def downgrade():
    op.drop_index("ix_promotional_kits_slug", table_name="promotional_kits")
    op.drop_column("promotional_kits", "video_url")
    op.drop_column("promotional_kits", "image_url")
    op.drop_column("promotional_kits", "slug")
