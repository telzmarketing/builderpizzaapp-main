"""Add a dedicated RBAC permission for strategic campaign publication."""

from alembic import op


revision = "20261126_strategic_campaign_publish_rbac_c9"
down_revision = "20261126_strategic_operations_c7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO rbac_permissions (id, key, name, description)
        VALUES (
            'rbac-permission-publish',
            'publish',
            'Publicar',
            'Publicar uma versao imutavel de conteudo comercial'
        )
        ON CONFLICT (key) DO UPDATE
        SET name = EXCLUDED.name,
            description = EXCLUDED.description
        """
    )
    op.execute(
        """
        INSERT INTO role_permissions (
            id, tenant_id, role_id, module_id, permission_id, allowed
        )
        SELECT
            'strategic-publish-' || md5(r.tenant_id || r.id || m.id || p.id),
            r.tenant_id,
            r.id,
            m.id,
            p.id,
            TRUE
        FROM roles r
        CROSS JOIN rbac_modules m
        CROSS JOIN rbac_permissions p
        WHERE lower(r.name) IN ('master', 'administrador')
          AND m.key = 'marketing'
          AND p.key = 'publish'
          AND NOT EXISTS (
              SELECT 1
              FROM role_permissions existing
              WHERE existing.tenant_id = r.tenant_id
                AND existing.role_id = r.id
                AND existing.module_id = m.id
                AND existing.permission_id = p.id
          )
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM role_permissions WHERE id LIKE 'strategic-publish-%'")
    op.execute(
        """
        DELETE FROM rbac_permissions permission
        WHERE permission.key = 'publish'
          AND NOT EXISTS (
              SELECT 1
              FROM role_permissions grant_row
              WHERE grant_row.permission_id = permission.id
          )
          AND NOT EXISTS (
              SELECT 1
              FROM user_permissions override_row
              WHERE override_row.permission_id = permission.id
          )
        """
    )
