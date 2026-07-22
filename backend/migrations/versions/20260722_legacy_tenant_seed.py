"""Seed the legacy tenant, memberships and minimum platform RBAC catalog.

Revision ID: 20260722_legacy_tenant_seed
Revises: 20260721_multi_tenant_foundation
Create Date: 2026-07-22

This data migration is additive and idempotent. It does not tenantize business
tables and does not change or remove legacy admin identities.
"""
from alembic import op


revision = "20260722_legacy_tenant_seed"
down_revision = "20260721_multi_tenant_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Stable IDs are part of the bootstrap contract used by the backend and by
    # the future VPS installer. ON CONFLICT makes a partially repeated seed safe.
    op.execute(
        """
        INSERT INTO tenants (
            id, slug, name, legal_name, status, timezone, locale, is_legacy,
            created_at, updated_at
        ) VALUES (
            'tenant-legacy-default', 'legacy', 'Empresa Legada', NULL, 'active',
            'America/Sao_Paulo', 'pt-BR', TRUE, NOW(), NOW()
        )
        ON CONFLICT DO NOTHING
        """
    )

    op.execute(
        """
        INSERT INTO platform_roles (id, key, name, description, is_system, created_at, updated_at)
        VALUES
            ('platform-role-owner', 'platform_owner', 'Proprietario da Plataforma',
             'Acesso total e explicito a administracao da plataforma.', TRUE, NOW(), NOW()),
            ('platform-role-admin', 'platform_admin', 'Administrador da Plataforma',
             'Administra empresas e operacao da plataforma.', TRUE, NOW(), NOW()),
            ('platform-role-support', 'platform_support', 'Suporte da Plataforma',
             'Acesso restrito a suporte e diagnostico auditado.', TRUE, NOW(), NOW())
        ON CONFLICT DO NOTHING
        """
    )

    op.execute(
        """
        INSERT INTO platform_permissions (id, key, name, description, created_at)
        VALUES
            ('platform-permission-tenants-view', 'tenants.view', 'Visualizar empresas',
             'Permite consultar empresas da plataforma.', NOW()),
            ('platform-permission-tenants-manage', 'tenants.manage', 'Gerenciar empresas',
             'Permite criar e administrar empresas da plataforma.', NOW()),
            ('platform-permission-audit-view', 'audit.view', 'Visualizar auditoria',
             'Permite consultar a auditoria da plataforma.', NOW()),
            ('platform-permission-support-impersonate', 'support.impersonate', 'Impersonar para suporte',
             'Permite iniciar suporte impersonado, sempre auditado.', NOW())
        ON CONFLICT DO NOTHING
        """
    )

    # Owner: all permissions. Admin: tenant management and audit. Support:
    # tenant lookup, audit and impersonation. Links resolve catalog rows by key
    # so an interrupted/retried seed remains deterministic.
    op.execute(
        """
        INSERT INTO platform_role_permissions (id, role_id, permission_id, created_at)
        SELECT
            'platform-rp-' || replace(r.key, 'platform_', '') || '-' || replace(p.key, '.', '-'),
            r.id, p.id, NOW()
        FROM platform_roles r
        CROSS JOIN platform_permissions p
        WHERE
            (r.key = 'platform_owner' AND p.key IN ('tenants.view', 'tenants.manage', 'audit.view', 'support.impersonate'))
            OR (r.key = 'platform_admin' AND p.key IN ('tenants.view', 'tenants.manage', 'audit.view'))
            OR (r.key = 'platform_support' AND p.key IN ('tenants.view', 'audit.view', 'support.impersonate'))
        ON CONFLICT DO NOTHING
        """
    )

    # Preserve the current authorization semantics:
    # no legacy role or master => owner; administrador => admin; gerente =>
    # manager; all other assigned roles => operator. Inactive users remain
    # represented but suspended and cannot be selected as default.
    op.execute(
        """
        INSERT INTO tenant_memberships (
            id, tenant_id, user_id, role, status, is_default, invited_by,
            joined_at, created_at, updated_at
        )
        SELECT
            'membership-legacy-' || substr(md5(u.id), 1, 24),
            'tenant-legacy-default',
            u.id,
            CASE
                WHEN u.role_id IS NULL OR lower(COALESCE(r.name, '')) = 'master' THEN 'owner'
                WHEN lower(COALESCE(r.name, '')) = 'administrador' THEN 'admin'
                WHEN lower(COALESCE(r.name, '')) = 'gerente' THEN 'manager'
                ELSE 'operator'
            END,
            CASE WHEN COALESCE(u.active, TRUE) THEN 'active' ELSE 'suspended' END,
            COALESCE(u.active, TRUE),
            NULL,
            CASE WHEN COALESCE(u.active, TRUE) THEN NOW() ELSE NULL END,
            NOW(),
            NOW()
        FROM admin_users u
        LEFT JOIN roles r ON r.id = u.role_id
        ON CONFLICT DO NOTHING
        """
    )

    # Platform authority is deliberately narrower than tenant ownership: only
    # users considered legacy masters receive platform_owner automatically.
    op.execute(
        """
        INSERT INTO platform_user_roles (id, user_id, role_id, granted_by, created_at)
        SELECT
            'platform-user-owner-' || substr(md5(u.id), 1, 24),
            u.id,
            pr.id,
            NULL,
            NOW()
        FROM admin_users u
        LEFT JOIN roles r ON r.id = u.role_id
        JOIN platform_roles pr ON pr.key = 'platform_owner'
        WHERE u.role_id IS NULL OR lower(COALESCE(r.name, '')) = 'master'
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    # Never remove admin_users or legacy RBAC data. Prefix + known role/tenant
    # boundaries ensure only rows owned by this migration are reverted.
    op.execute(
        """
        DELETE FROM platform_user_roles
        WHERE id LIKE 'platform-user-owner-%'
          AND role_id IN (
              SELECT id FROM platform_roles
              WHERE id = 'platform-role-owner' AND key = 'platform_owner'
          )
        """
    )
    op.execute(
        """
        DELETE FROM tenant_memberships
        WHERE tenant_id = 'tenant-legacy-default'
          AND id LIKE 'membership-legacy-%'
        """
    )
    op.execute(
        """
        DELETE FROM platform_role_permissions
        WHERE id IN (
            'platform-rp-owner-tenants-view',
            'platform-rp-owner-tenants-manage',
            'platform-rp-owner-audit-view',
            'platform-rp-owner-support-impersonate',
            'platform-rp-admin-tenants-view',
            'platform-rp-admin-tenants-manage',
            'platform-rp-admin-audit-view',
            'platform-rp-support-tenants-view',
            'platform-rp-support-audit-view',
            'platform-rp-support-support-impersonate'
        )
        """
    )
    op.execute(
        """
        DELETE FROM platform_permissions
        WHERE id IN (
            'platform-permission-tenants-view',
            'platform-permission-tenants-manage',
            'platform-permission-audit-view',
            'platform-permission-support-impersonate'
        )
        """
    )
    op.execute(
        """
        DELETE FROM platform_roles
        WHERE id IN ('platform-role-owner', 'platform-role-admin', 'platform-role-support')
        """
    )
    op.execute(
        """
        DELETE FROM tenants
        WHERE id = 'tenant-legacy-default' AND slug = 'legacy' AND is_legacy = TRUE
        """
    )
