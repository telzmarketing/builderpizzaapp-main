from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from backend.config import get_settings
from backend.database import Base

# Import models so Alembic can detect metadata for autogenerate.
from backend.models import (  # noqa: F401
    admin,
    agente_whatsapp,
    campaign,
    chatbot,
    business_intelligence,
    cmv,
    coupon,
    crm,
    customer,
    customer_contact_risk,
    customer_event,
    customer_identity,
    delivery,
    finance,
    fiscal,
    gestao,
    home_config,
    idempotency,
    inventory,
    loyalty,
    marketing_intelligence,
    order,
    paid_traffic,
    payment,
    payment_config,
    product,
    product_promotion,
    promotion,
    promotion_landing_page,
    rbac,
    salao,
    salao_page,
    shipping,
    shipping_v2,
    store_operation,
    store_notification,
    theme,
    tenant,
    tenant_domain,
    upsell,
    membership,
    platform_rbac,
    platform_audit,
    platform_operations,
    platform_saas,
    whatsapp_gateway,
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().DATABASE_URL)
target_metadata = Base.metadata


class _OfflineScalarResult:
    """Minimal result used while migration preflights are rendered as SQL."""

    def __init__(self, value=None, rows=()):
        self._value = value
        self._rows = tuple(rows)

    def scalar(self):
        return self._value

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)


def _configure_offline_preflight_adapter() -> None:
    """Make data-aware historical migrations renderable in ``--sql`` mode.

    Alembic's mock connection cannot return rows.  Read-only preflight SELECTs
    are therefore emitted as PostgreSQL guards and receive a deterministic
    result only to let Python continue rendering the remaining DDL/DML.
    """
    connection = context.get_context().connection
    original_execute = connection.execute

    def execute(statement, *multiparams, **params):
        sql = str(statement).strip()
        upper = sql.upper()
        bound = multiparams[0] if multiparams and isinstance(multiparams[0], dict) else params
        if upper.startswith("SELECT"):
            rendered = sql
            for key, value in (bound or {}).items():
                literal = "NULL" if value is None else "'" + str(value).replace("'", "''") + "'"
                rendered = rendered.replace(f":{key}", literal)
            expects_existing_tenant = "FROM TENANTS" in upper and "LEFT JOIN" not in upper
            if "FROM PG_CONSTRAINT" in upper:
                table = str((bound or {}).get("table") or "").replace("'", "''")
                original_execute(
                    "DO $alembic$ DECLARE item record; BEGIN FOR item IN "
                    "SELECT con.conname FROM pg_constraint con "
                    "JOIN pg_class rel ON rel.oid=con.conrelid "
                    "JOIN pg_namespace ns ON ns.oid=rel.relnamespace "
                    f"WHERE ns.nspname=current_schema() AND rel.relname='{table}' "
                    "AND con.contype='f' AND NOT con.convalidated LOOP "
                    f"EXECUTE format('ALTER TABLE %I VALIDATE CONSTRAINT %I', '{table}', item.conname); "
                    "END LOOP; END $alembic$;"
                )
            elif expects_existing_tenant:
                original_execute(
                    "DO $alembic$ BEGIN IF NOT EXISTS (" + rendered.rstrip(";")
                    + ") THEN RAISE EXCEPTION 'Alembic offline required row is missing'; END IF; END $alembic$;"
                )
            elif not upper.startswith("SELECT COUNT("):
                original_execute(
                    "DO $alembic$ BEGIN IF EXISTS (" + rendered.rstrip(";")
                    + ") THEN RAISE EXCEPTION 'Alembic offline preflight failed'; END IF; END $alembic$;"
                )
            if upper.startswith("SELECT COUNT(") or expects_existing_tenant:
                return _OfflineScalarResult(1)
            return _OfflineScalarResult()
        return original_execute(statement, *multiparams, **params)

    connection.execute = execute
    connection.exec_driver_sql = execute


def run_migrations_offline() -> None:
    context.configure(
        url=get_settings().DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    _configure_offline_preflight_adapter()

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
