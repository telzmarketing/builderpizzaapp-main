"""Allow the two fixed pizza benches in the existing KDS station contract."""

from alembic import op


revision = "20261104_fixed_pizza_stations"
down_revision = "20261103_production_vision_expansion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_production_unit_station", "production_units", type_="check")
    op.create_check_constraint(
        "ck_production_unit_station",
        "production_units",
        "station_id IN ('pizza','pizza-1','pizza-2','esfiha','expedicao')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_production_unit_station", "production_units", type_="check")
    op.create_check_constraint(
        "ck_production_unit_station",
        "production_units",
        "station_id IN ('pizza','esfiha','expedicao')",
    )
