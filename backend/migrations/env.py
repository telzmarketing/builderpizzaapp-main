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


def run_migrations_offline() -> None:
    context.configure(
        url=get_settings().DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

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
