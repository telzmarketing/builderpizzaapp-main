"""Persist operational production stations on physical KDS units.

This is additive and forward-only: commercial orders remain unchanged and
existing non-drink kitchen units retain the pizzaiolo station.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261101_kds_production_stations"
down_revision = "20261030_order_origins_partner_identifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("production_units", sa.Column("station_id", sa.String(20), nullable=False, server_default="pizza"))
    op.create_check_constraint(
        "ck_production_unit_station", "production_units",
        "station_id IN ('pizza','esfiha','expedicao')",
    )
    op.create_index("ix_production_units_tenant_station_queue", "production_units", ["tenant_id", "station_id", "state", "created_at"])
    op.execute(sa.text("""
        UPDATE production_units AS u
        SET station_id = CASE
            WHEN p.product_type = 'esfiha' THEN 'esfiha'
            WHEN p.product_type = 'drink' OR oi.selected_drink_variant IS NOT NULL THEN 'expedicao'
            ELSE 'pizza'
        END
        FROM order_items oi
        LEFT JOIN products p ON p.id = oi.product_id AND p.tenant_id IS NOT DISTINCT FROM oi.tenant_id
        WHERE oi.id = u.order_item_id AND oi.tenant_id = u.tenant_id
    """))


def downgrade() -> None:
    op.drop_index("ix_production_units_tenant_station_queue", table_name="production_units")
    op.drop_constraint("ck_production_unit_station", "production_units", type_="check")
    op.drop_column("production_units", "station_id")
