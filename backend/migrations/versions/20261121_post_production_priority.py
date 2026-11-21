"""Persist priority for replacement production created by amendments."""

from alembic import op
import sqlalchemy as sa

revision = "20261121_post_production_priority"
down_revision = "20261121_post_production_amendment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("production_attempts", sa.Column("priority", sa.Integer(), nullable=False, server_default="0"))
    op.create_check_constraint("ck_production_attempt_priority", "production_attempts", "priority >= 0")


def downgrade() -> None:
    # Priority is operational state: dropping it can cause a queued remake to
    # lose its required position ahead of untouched work.
    if not op.get_context().as_sql:
        has_priority = op.get_bind().execute(sa.text(
            "SELECT EXISTS (SELECT 1 FROM production_attempts WHERE priority > 0)"
        )).scalar()
        if has_priority:
            raise RuntimeError(
                "Refusing to downgrade production attempt priority while prioritized work exists"
            )

    op.drop_constraint("ck_production_attempt_priority", "production_attempts", type_="check")
    op.drop_column("production_attempts", "priority")
