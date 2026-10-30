"""Distinguish dough and border options without guessing from names.

Compatibility: all existing rows and inserts omitting option_kind become dough.
IDs and order snapshots remain unchanged. Operators can explicitly reclassify
known borders through the catalog update API, keeping their original IDs.
Apply before starting the updated backend. This migration is forward-only:
downgrading would discard classifications used by live orders and catalog APIs.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261030_crust_option_kind"
down_revision = "20261029_customer_commercial_memory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("product_crust_types", sa.Column(
        "option_kind", sa.String(10), nullable=False, server_default="dough",
    ))
    op.create_check_constraint(
        "ck_product_crust_types_option_kind", "product_crust_types",
        "option_kind IN ('dough', 'border')",
    )


def downgrade() -> None:
    raise RuntimeError("Forward-only migration: option_kind classifications must be preserved.")
