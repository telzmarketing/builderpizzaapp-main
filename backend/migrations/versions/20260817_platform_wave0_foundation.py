"""Seed future Master Central permissions with least-privilege role grants.

Revision ID: 20260817_platform_wave0
Revises: 20260816_master_completion

This migration only extends the platform RBAC catalog. It does not publish
routes or enable unavailable Central Master modules.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260817_platform_wave0"
down_revision = "20260816_master_completion"
branch_labels = None
depends_on = None


PERMISSIONS = (
    ("platform_users.view", "Visualizar usuarios da plataforma", "Consulta identidades e papeis da plataforma."),
    ("platform_users.manage", "Gerenciar usuarios da plataforma", "Administra identidades e papeis da plataforma."),
    ("platform_settings.view", "Visualizar configuracoes da plataforma", "Consulta configuracoes operacionais permitidas."),
    ("platform_settings.manage", "Gerenciar configuracoes da plataforma", "Altera configuracoes operacionais permitidas."),
    ("monitoring.view", "Visualizar saude dos servicos", "Consulta saude e disponibilidade dos servicos."),
    ("integrations.view", "Visualizar integracoes", "Consulta o estado redigido das integracoes."),
    ("integrations.manage", "Gerenciar integracoes", "Executa acoes permitidas nas integracoes."),
    ("jobs.view", "Visualizar filas e jobs", "Consulta filas, jobs e workers."),
    ("jobs.manage", "Gerenciar filas e jobs", "Executa acoes permitidas em filas e jobs."),
    ("gateway.view", "Visualizar WhatsApp Gateway", "Consulta a frota e a saude do WhatsApp Gateway."),
    ("gateway.manage", "Gerenciar WhatsApp Gateway", "Executa acoes permitidas no WhatsApp Gateway."),
    ("errors.view", "Visualizar erros", "Consulta erros operacionais redigidos."),
    ("errors.manage", "Gerenciar erros", "Classifica e reconhece erros operacionais."),
    ("storage.view", "Visualizar armazenamento", "Consulta consumo e limites de armazenamento."),
    ("backups.view", "Visualizar backups", "Consulta metadados e validacoes de backups."),
)


ROLE_GRANTS = {
    "platform_owner": tuple(key for key, _name, _description in PERMISSIONS),
    "platform_admin": (
        "platform_users.view",
        "platform_settings.view",
        "monitoring.view",
        "integrations.view",
        "integrations.manage",
        "jobs.view",
        "jobs.manage",
        "gateway.view",
        "gateway.manage",
        "errors.view",
        "errors.manage",
        "storage.view",
        "backups.view",
    ),
    "platform_support": (
        "monitoring.view",
        "integrations.view",
        "jobs.view",
        "gateway.view",
        "errors.view",
    ),
}


def _permission_id(key: str) -> str:
    return f"platform-permission-{key.replace('.', '-')}"


def _grant_id(role_key: str, permission_key: str) -> str:
    role = role_key.removeprefix("platform_")
    permission = permission_key.replace(".", "-")
    return f"platform-rp-wave0-{role}-{permission}"


def _quoted(value: str) -> str:
    # All values are migration-owned constants. Quoting here also keeps the
    # generated SQL valid if a future description contains an apostrophe.
    return "'" + value.replace("'", "''") + "'"


def upgrade() -> None:
    permissions = sa.table(
        "platform_permissions",
        sa.column("id", sa.String()),
        sa.column("key", sa.String()),
        sa.column("name", sa.String()),
        sa.column("description", sa.Text()),
    )
    rows = [
        {
            "id": _permission_id(key),
            "key": key,
            "name": name,
            "description": description,
        }
        for key, name, description in PERMISSIONS
    ]
    op.get_bind().execute(
        postgresql.insert(permissions)
        .values(rows)
        .on_conflict_do_nothing(index_elements=["key"])
    )

    # Missing system roles would leave the control plane in a misleading
    # partially seeded state, so fail the migration before creating grants.
    op.execute(
        """
        DO $$
        BEGIN
            IF (
                SELECT count(*)
                FROM platform_roles
                WHERE key IN ('platform_owner', 'platform_admin', 'platform_support')
            ) <> 3 THEN
                RAISE EXCEPTION 'Platform system roles are incomplete';
            END IF;
        END $$
        """
    )

    grant_rows = [
        (_grant_id(role_key, permission_key), role_key, permission_key)
        for role_key, permission_keys in ROLE_GRANTS.items()
        for permission_key in permission_keys
    ]
    grant_values = ",\n                ".join(
        f"({_quoted(grant_id)}, {_quoted(role_key)}, {_quoted(permission_key)})"
        for grant_id, role_key, permission_key in grant_rows
    )
    op.execute(
        f"""
        INSERT INTO platform_role_permissions (
            id, role_id, permission_id, created_at
        )
        SELECT grants.id, roles.id, permissions.id, NOW()
        FROM (
            VALUES
                {grant_values}
        ) AS grants(id, role_key, permission_key)
        JOIN platform_roles roles ON roles.key = grants.role_key
        JOIN platform_permissions permissions ON permissions.key = grants.permission_key
        ON CONFLICT (role_id, permission_id) DO NOTHING
        """
    )


def downgrade() -> None:
    grant_ids = [
        _grant_id(role_key, permission_key)
        for role_key, permission_keys in ROLE_GRANTS.items()
        for permission_key in permission_keys
    ]
    op.execute(
        f"""
        DELETE FROM platform_role_permissions
        WHERE id IN ({', '.join(_quoted(value) for value in grant_ids)})
        """
    )

    permission_pairs = ", ".join(
        f"({_quoted(_permission_id(key))}, {_quoted(key)})"
        for key, _name, _description in PERMISSIONS
    )
    # Preserve a permission if a later role started referencing it. Downgrade
    # only removes catalog rows owned by this migration and no longer in use.
    op.execute(
        f"""
        DELETE FROM platform_permissions permissions
        WHERE (permissions.id, permissions.key) IN (VALUES {permission_pairs})
          AND NOT EXISTS (
              SELECT 1
              FROM platform_role_permissions grants
              WHERE grants.permission_id = permissions.id
          )
        """
    )
