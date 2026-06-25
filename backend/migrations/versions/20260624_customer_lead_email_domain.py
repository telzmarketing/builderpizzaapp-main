"""customer lead email domain

Revision ID: 20260624_customer_lead_email_domain
Revises: 20260613_marketing_intelligence_goals_timeline
"""
from __future__ import annotations

from alembic import op

revision = "20260624_customer_lead_email_domain"
down_revision = "20260613_marketing_intelligence_goals_timeline"
branch_labels = None
depends_on = None

OLD_DOMAIN = "lead.whatsapp.local"
NEW_DOMAIN = "leads.moschettieri.com.br"


def upgrade() -> None:
    op.execute(
        f"""
        UPDATE customers
        SET email = regexp_replace(email, '@{OLD_DOMAIN}$', '@{NEW_DOMAIN}')
        WHERE email LIKE '%@{OLD_DOMAIN}'
        """
    )
    op.execute(
        f"""
        UPDATE customer_channels
        SET identifier = regexp_replace(identifier, '@{OLD_DOMAIN}$', '@{NEW_DOMAIN}'),
            normalized_identifier = regexp_replace(normalized_identifier, '@{OLD_DOMAIN}$', '@{NEW_DOMAIN}')
        WHERE channel = 'email'
          AND identifier LIKE '%@{OLD_DOMAIN}'
        """
    )
    op.execute(
        f"""
        UPDATE customer_auth
        SET identifier = regexp_replace(identifier, '@{OLD_DOMAIN}$', '@{NEW_DOMAIN}')
        WHERE auth_provider = 'password'
          AND identifier LIKE '%@{OLD_DOMAIN}'
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        UPDATE customer_auth
        SET identifier = regexp_replace(identifier, '@{NEW_DOMAIN}$', '@{OLD_DOMAIN}')
        WHERE auth_provider = 'password'
          AND identifier LIKE '%@{NEW_DOMAIN}'
        """
    )
    op.execute(
        f"""
        UPDATE customer_channels
        SET identifier = regexp_replace(identifier, '@{NEW_DOMAIN}$', '@{OLD_DOMAIN}'),
            normalized_identifier = regexp_replace(normalized_identifier, '@{NEW_DOMAIN}$', '@{OLD_DOMAIN}')
        WHERE channel = 'email'
          AND identifier LIKE '%@{NEW_DOMAIN}'
        """
    )
    op.execute(
        f"""
        UPDATE customers
        SET email = regexp_replace(email, '@{NEW_DOMAIN}$', '@{OLD_DOMAIN}')
        WHERE email LIKE '%@{NEW_DOMAIN}'
        """
    )
