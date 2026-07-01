"""gestao fiscal sefaz base

Revision ID: 20260630_gestao_fiscal_sefaz_base
Revises: 20260630_gestao_finance_phase8_management
"""
from __future__ import annotations

from alembic import op

revision = "20260630_gestao_fiscal_sefaz_base"
down_revision = "20260630_gestao_finance_phase8_management"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS fiscal_companies (
            id VARCHAR PRIMARY KEY,
            tenant_id VARCHAR(80) NOT NULL DEFAULT 'default',
            legal_name VARCHAR(220) NOT NULL,
            trade_name VARCHAR(220),
            document VARCHAR(20) NOT NULL,
            state_registration VARCHAR(40),
            municipal_registration VARCHAR(40),
            tax_regime VARCHAR(40) NOT NULL DEFAULT 'simples_nacional',
            cnae VARCHAR(20),
            address_street VARCHAR(220),
            address_number VARCHAR(40),
            address_complement VARCHAR(120),
            neighborhood VARCHAR(120),
            city VARCHAR(120),
            city_ibge_code VARCHAR(20),
            state VARCHAR(2),
            zip_code VARCHAR(20),
            phone VARCHAR(40),
            email VARCHAR(180),
            active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_fiscal_companies_tenant_id ON fiscal_companies(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_fiscal_companies_document ON fiscal_companies(document)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS fiscal_certificates (
            id VARCHAR PRIMARY KEY,
            tenant_id VARCHAR(80) NOT NULL DEFAULT 'default',
            certificate_type VARCHAR(20) NOT NULL DEFAULT 'a1',
            subject_name VARCHAR(220),
            serial_number VARCHAR(120),
            valid_from DATE,
            valid_until DATE,
            storage_reference VARCHAR(220),
            password_configured BOOLEAN NOT NULL DEFAULT FALSE,
            active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_fiscal_certificates_tenant_id ON fiscal_certificates(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_fiscal_certificates_serial_number ON fiscal_certificates(serial_number)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_fiscal_certificates_valid_until ON fiscal_certificates(valid_until)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_fiscal_certificates_active ON fiscal_certificates(active)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS fiscal_series (
            id VARCHAR PRIMARY KEY,
            tenant_id VARCHAR(80) NOT NULL DEFAULT 'default',
            document_model VARCHAR(10) NOT NULL DEFAULT 'NFCe',
            series VARCHAR(10) NOT NULL,
            environment VARCHAR(20) NOT NULL DEFAULT 'homologation',
            next_number INTEGER NOT NULL DEFAULT 1,
            active BOOLEAN NOT NULL DEFAULT TRUE,
            notes TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_fiscal_series_tenant_id ON fiscal_series(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_fiscal_series_document_model ON fiscal_series(document_model)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_fiscal_series_series ON fiscal_series(series)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_fiscal_series_environment ON fiscal_series(environment)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_fiscal_series_active ON fiscal_series(active)")
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_fiscal_series_scope
        ON fiscal_series(tenant_id, document_model, series, environment)
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS fiscal_product_profiles (
            id VARCHAR PRIMARY KEY,
            tenant_id VARCHAR(80) NOT NULL DEFAULT 'default',
            product_id VARCHAR NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            ncm VARCHAR(10) NOT NULL,
            cest VARCHAR(10),
            cfop VARCHAR(10) NOT NULL DEFAULT '5102',
            origin VARCHAR(2) NOT NULL DEFAULT '0',
            cst VARCHAR(4),
            csosn VARCHAR(4),
            icms_rate FLOAT NOT NULL DEFAULT 0,
            pis_cst VARCHAR(4),
            pis_rate FLOAT NOT NULL DEFAULT 0,
            cofins_cst VARCHAR(4),
            cofins_rate FLOAT NOT NULL DEFAULT 0,
            fiscal_description VARCHAR(220),
            active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_fiscal_product_profiles_tenant_id ON fiscal_product_profiles(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_fiscal_product_profiles_product_id ON fiscal_product_profiles(product_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_fiscal_product_profiles_active ON fiscal_product_profiles(active)")
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_fiscal_product_profiles_product
        ON fiscal_product_profiles(tenant_id, product_id)
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS fiscal_documents (
            id VARCHAR PRIMARY KEY,
            tenant_id VARCHAR(80) NOT NULL DEFAULT 'default',
            order_id VARCHAR REFERENCES orders(id) ON DELETE SET NULL,
            company_id VARCHAR REFERENCES fiscal_companies(id) ON DELETE SET NULL,
            series_id VARCHAR REFERENCES fiscal_series(id) ON DELETE SET NULL,
            document_model VARCHAR(10) NOT NULL DEFAULT 'NFCe',
            environment VARCHAR(20) NOT NULL DEFAULT 'homologation',
            status VARCHAR(40) NOT NULL DEFAULT 'draft',
            operation_type VARCHAR(40) NOT NULL DEFAULT 'sale',
            series VARCHAR(10),
            number INTEGER,
            access_key VARCHAR(60),
            issue_date TIMESTAMPTZ,
            customer_name VARCHAR(220),
            customer_document VARCHAR(40),
            total_products FLOAT NOT NULL DEFAULT 0,
            total_shipping FLOAT NOT NULL DEFAULT 0,
            total_discount FLOAT NOT NULL DEFAULT 0,
            total_document FLOAT NOT NULL DEFAULT 0,
            xml_content TEXT,
            signed_xml_content TEXT,
            protocol VARCHAR(120),
            rejection_reason TEXT,
            cancellation_protocol VARCHAR(120),
            inutilization_protocol VARCHAR(120),
            sefaz_status_code VARCHAR(20),
            sefaz_status_message TEXT,
            snapshot_json TEXT NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_fiscal_documents_tenant_id ON fiscal_documents(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_fiscal_documents_order_id ON fiscal_documents(order_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_fiscal_documents_company_id ON fiscal_documents(company_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_fiscal_documents_series_id ON fiscal_documents(series_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_fiscal_documents_document_model ON fiscal_documents(document_model)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_fiscal_documents_environment ON fiscal_documents(environment)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_fiscal_documents_status ON fiscal_documents(status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_fiscal_documents_number ON fiscal_documents(number)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_fiscal_documents_access_key ON fiscal_documents(access_key)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_fiscal_documents_issue_date ON fiscal_documents(issue_date)")
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_fiscal_documents_number
        ON fiscal_documents(tenant_id, document_model, environment, series, number)
        WHERE number IS NOT NULL
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS fiscal_document_items (
            id VARCHAR PRIMARY KEY,
            document_id VARCHAR NOT NULL REFERENCES fiscal_documents(id) ON DELETE CASCADE,
            product_id VARCHAR REFERENCES products(id) ON DELETE SET NULL,
            description VARCHAR(220) NOT NULL,
            quantity FLOAT NOT NULL DEFAULT 1,
            unit_price FLOAT NOT NULL DEFAULT 0,
            total_price FLOAT NOT NULL DEFAULT 0,
            ncm VARCHAR(10),
            cest VARCHAR(10),
            cfop VARCHAR(10),
            origin VARCHAR(2),
            cst VARCHAR(4),
            csosn VARCHAR(4),
            icms_rate FLOAT NOT NULL DEFAULT 0,
            pis_cst VARCHAR(4),
            pis_rate FLOAT NOT NULL DEFAULT 0,
            cofins_cst VARCHAR(4),
            cofins_rate FLOAT NOT NULL DEFAULT 0,
            tax_profile_snapshot_json TEXT NOT NULL DEFAULT '{}'
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_fiscal_document_items_document_id ON fiscal_document_items(document_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_fiscal_document_items_product_id ON fiscal_document_items(product_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS fiscal_document_events (
            id VARCHAR PRIMARY KEY,
            tenant_id VARCHAR(80) NOT NULL DEFAULT 'default',
            document_id VARCHAR NOT NULL REFERENCES fiscal_documents(id) ON DELETE CASCADE,
            event_type VARCHAR(40) NOT NULL,
            status VARCHAR(40) NOT NULL DEFAULT 'recorded',
            request_xml TEXT,
            response_xml TEXT,
            protocol VARCHAR(120),
            message TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_fiscal_document_events_tenant_id ON fiscal_document_events(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_fiscal_document_events_document_id ON fiscal_document_events(document_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_fiscal_document_events_event_type ON fiscal_document_events(event_type)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_fiscal_document_events_status ON fiscal_document_events(status)")

    op.execute(
        """
        UPDATE gestao_module_settings
        SET settings_json = (
            COALESCE(settings_json::jsonb, '{}'::jsonb)
            || '{"sefaz_integration_enabled": false, "environment": "homologation", "certificate_configured": false, "external_middleware_allowed": false, "default_document_model": "NFCe"}'::jsonb
        )::text
        WHERE module_key = 'fiscal'
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS fiscal_document_events")
    op.execute("DROP TABLE IF EXISTS fiscal_document_items")
    op.execute("DROP TABLE IF EXISTS fiscal_documents")
    op.execute("DROP TABLE IF EXISTS fiscal_product_profiles")
    op.execute("DROP TABLE IF EXISTS fiscal_series")
    op.execute("DROP TABLE IF EXISTS fiscal_certificates")
    op.execute("DROP TABLE IF EXISTS fiscal_companies")
