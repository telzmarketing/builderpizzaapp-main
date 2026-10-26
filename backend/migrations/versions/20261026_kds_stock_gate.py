"""Persist the five-second KDS stock gate and operational analysis queue."""
from alembic import op
import sqlalchemy as sa

revision = "20261026_kds_stock_gate"
down_revision = "20261026_customer_phone_lgpd_scope"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("production_attempts", sa.Column("stock_requested_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("production_attempts", sa.Column("stock_check_after", sa.DateTime(timezone=True), nullable=True))
    op.add_column("production_attempts", sa.Column("stock_consumption_mode", sa.String(30), nullable=True))
    states = "'queued','checking_stock','aguardando_analise','atendimento','assembling','assembled','baking','checking','ready','blocked','cancelled'"
    op.drop_constraint("ck_production_attempt_state", "production_attempts", type_="check")
    op.create_check_constraint("ck_production_attempt_state", "production_attempts", f"state IN ({states})")
    op.drop_constraint("ck_production_unit_state", "production_units", type_="check")
    op.create_check_constraint("ck_production_unit_state", "production_units", f"state IN ('unassigned',{states})")
    op.create_index("ix_production_attempts_stock_queue", "production_attempts", ["tenant_id", "state", "stock_requested_at"])


def downgrade():
    raise RuntimeError("Forward-only: preserve stock requests, analysis and consumption history.")
