"""Classify unambiguous pre-option_kind border rows.

The option_kind migration intentionally defaulted existing rows to ``dough``
because names are not a reliable discriminator in general.  This follow-up
backfill handles only the legacy display names that are explicitly prefixed by
``Borda`` (after trimming and case folding).  It is deliberately narrow:
``Sem borda`` and every other name remain unchanged for manual review.

The predicate is also idempotent, so re-running the data statement cannot
change rows already classified as border or revisit any other option.
"""
from alembic import op


revision = "20261030_backfill_legacy_border_option_kind"
down_revision = "20261030_crust_option_kind"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE product_crust_types
        SET option_kind = 'border'
        WHERE option_kind = 'dough'
          AND (
              lower(trim(name)) = 'borda'
              OR lower(trim(name)) LIKE 'borda %'
          )
        """
    )


def downgrade() -> None:
    raise RuntimeError(
        "Forward-only migration: legacy border classifications must be preserved."
    )
