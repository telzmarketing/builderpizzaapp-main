"""Enforce normalized tenant phone identity and nullable admin email."""
from alembic import op
import sqlalchemy as sa


revision = "20261026_customer_phone_lgpd_scope"
down_revision = "20261022_receipt_pdf_camera_evidence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("customers", sa.Column("normalized_phone", sa.String(30), nullable=True))
    op.alter_column("customers", "email", existing_type=sa.String(length=200), nullable=True)
    # Existing formatted phone values are canonicalized before the unique index.
    op.execute(
        "UPDATE customers SET normalized_phone = regexp_replace(phone, '[^0-9]', '', 'g') "
        "WHERE phone IS NOT NULL AND phone <> ''"
    )
    duplicate = op.get_bind().execute(sa.text(
        "SELECT tenant_id, normalized_phone FROM customers "
        "WHERE normalized_phone IS NOT NULL AND normalized_phone <> '' "
        "GROUP BY tenant_id, normalized_phone HAVING COUNT(*) > 1 LIMIT 1"
    )).first()
    if duplicate:
        raise RuntimeError(
            "Customer phone identity migration found duplicate normalized phone "
            f"for tenant={duplicate[0]} phone={duplicate[1]}; resolve before retrying."
        )
    op.create_index(
        "uq_customers_tenant_normalized_phone",
        "customers",
        ["tenant_id", "normalized_phone"],
        unique=True,
        postgresql_where=sa.text("normalized_phone IS NOT NULL AND normalized_phone <> ''"),
    )


def downgrade() -> None:
    op.drop_index("uq_customers_tenant_normalized_phone", table_name="customers")
    op.alter_column("customers", "email", existing_type=sa.String(length=200), nullable=False)
    op.drop_column("customers", "normalized_phone")
