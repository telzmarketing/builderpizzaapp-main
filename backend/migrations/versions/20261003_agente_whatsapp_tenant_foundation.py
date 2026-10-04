"""Finish the database foundation for tenant-scoped Agente WhatsApp.

Revision ID: 20261003_agente_whatsapp_tenant_foundation
Revises: 20261003_email_marketing_tenant_config

The Wave 6 expand/backfill/contract migrations already introduced tenant_id and
composite ownership foreign keys.  This revision removes the few remaining
*global* uniqueness contracts that would either mix tenant queues or prevent
two companies from using the same provider identifiers.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20261003_agente_whatsapp_tenant_foundation"
down_revision = "20261003_email_marketing_tenant_config"
branch_labels = None
depends_on = None


TABLES = (
    "agente_whatsapp_sessions",
    "agente_whatsapp_ai_settings",
    "agente_whatsapp_channel_settings",
    "agente_whatsapp_messages",
    "agente_whatsapp_audio_artifacts",
    "agente_whatsapp_processing_jobs",
    "agente_whatsapp_outbox",
    "agente_whatsapp_provider_states",
    "agente_whatsapp_internal_alerts",
    "agente_whatsapp_events",
    "agente_whatsapp_context",
    "agente_whatsapp_tool_calls",
    "agente_whatsapp_metrics",
    "agente_whatsapp_campaigns",
    "agente_whatsapp_stories",
)

# Each tuple is a child table, a nullable FK column, and its parent table.
# The earlier Wave 6 migration installed composite FKs for these pairs; retain
# this explicit preflight so an old or manually altered database fails closed
# before its global keys are relaxed.
OWNERSHIP_PAIRS = (
    ("agente_whatsapp_sessions", "customer_id", "customers"),
    ("agente_whatsapp_channel_settings", "whatsapp_gateway_instance_id", "whatsapp_gateway_instances"),
    ("agente_whatsapp_messages", "session_id", "agente_whatsapp_sessions"),
    ("agente_whatsapp_messages", "customer_id", "customers"),
    ("agente_whatsapp_messages", "response_to_message_id", "agente_whatsapp_messages"),
    ("agente_whatsapp_messages", "campaign_id", "whatsapp_campaigns"),
    ("agente_whatsapp_messages", "campaign_delivery_id", "whatsapp_campaign_deliveries"),
    ("agente_whatsapp_audio_artifacts", "message_id", "agente_whatsapp_messages"),
    ("agente_whatsapp_processing_jobs", "message_id", "agente_whatsapp_messages"),
    ("agente_whatsapp_processing_jobs", "session_id", "agente_whatsapp_sessions"),
    ("agente_whatsapp_processing_jobs", "customer_id", "customers"),
    ("agente_whatsapp_outbox", "message_id", "agente_whatsapp_messages"),
    ("agente_whatsapp_outbox", "session_id", "agente_whatsapp_sessions"),
    ("agente_whatsapp_outbox", "customer_id", "customers"),
    ("agente_whatsapp_events", "session_id", "agente_whatsapp_sessions"),
    ("agente_whatsapp_events", "customer_id", "customers"),
    ("agente_whatsapp_events", "order_id", "orders"),
    ("agente_whatsapp_context", "session_id", "agente_whatsapp_sessions"),
    ("agente_whatsapp_context", "customer_id", "customers"),
    ("agente_whatsapp_tool_calls", "session_id", "agente_whatsapp_sessions"),
    ("agente_whatsapp_tool_calls", "customer_id", "customers"),
    ("agente_whatsapp_stories", "campaign_id", "agente_whatsapp_campaigns"),
)

SCOPED_UNIQUES = (
    ("uq_agente_whatsapp_messages_tenant_idempotency", "agente_whatsapp_messages", "tenant_id, idempotency_key", "idempotency_key IS NOT NULL"),
    ("uq_agente_whatsapp_jobs_tenant_idempotency", "agente_whatsapp_processing_jobs", "tenant_id, idempotency_key", None),
    ("uq_agente_whatsapp_outbox_tenant_idempotency", "agente_whatsapp_outbox", "tenant_id, idempotency_key", None),
    ("uq_agente_whatsapp_metrics_tenant_date", "agente_whatsapp_metrics", "tenant_id, date", None),
)

GLOBAL_CONSTRAINTS = (
    ("agente_whatsapp_processing_jobs", "agente_whatsapp_processing_jobs_idempotency_key_key"),
    ("agente_whatsapp_outbox", "agente_whatsapp_outbox_message_id_key"),
    ("agente_whatsapp_outbox", "agente_whatsapp_outbox_idempotency_key_key"),
    ("agente_whatsapp_provider_states", "agente_whatsapp_provider_states_provider_key"),
    ("agente_whatsapp_internal_alerts", "agente_whatsapp_internal_alerts_dedupe_key_key"),
    ("agente_whatsapp_context", "agente_whatsapp_context_session_id_key"),
)

PERFORMANCE_INDEXES = (
    ("ix_agente_whatsapp_sessions_tenant_phone", "agente_whatsapp_sessions", "tenant_id, phone"),
    ("ix_agente_whatsapp_messages_tenant_session_created", "agente_whatsapp_messages", "tenant_id, session_id, created_at DESC"),
    ("ix_agente_whatsapp_messages_tenant_provider_message", "agente_whatsapp_messages", "tenant_id, provider, provider_message_id"),
    ("ix_agente_whatsapp_audio_tenant_message", "agente_whatsapp_audio_artifacts", "tenant_id, message_id"),
    ("ix_agente_whatsapp_jobs_tenant_status_next_attempt", "agente_whatsapp_processing_jobs", "tenant_id, status, next_attempt_at"),
    ("ix_agente_whatsapp_outbox_tenant_status_next_attempt", "agente_whatsapp_outbox", "tenant_id, status, next_attempt_at"),
    ("ix_agente_whatsapp_events_tenant_session_created", "agente_whatsapp_events", "tenant_id, session_id, created_at DESC"),
    ("ix_agente_whatsapp_tool_calls_tenant_session_created", "agente_whatsapp_tool_calls", "tenant_id, session_id, created_at DESC"),
    ("ix_agente_whatsapp_campaigns_tenant_status", "agente_whatsapp_campaigns", "tenant_id, status"),
    ("ix_agente_whatsapp_stories_tenant_campaign", "agente_whatsapp_stories", "tenant_id, campaign_id"),
)


def _require_valid_tenant_ownership(bind) -> None:
    for table in TABLES:
        invalid = bind.execute(sa.text(
            f"SELECT 1 FROM {table} child "
            "LEFT JOIN tenants tenant ON tenant.id = child.tenant_id "
            "WHERE child.tenant_id IS NULL OR child.tenant_id = 'default' "
            "OR tenant.id IS NULL OR tenant.deleted_at IS NOT NULL LIMIT 1"
        )).scalar()
        if invalid is not None:
            raise RuntimeError(f"Agente WhatsApp: tenant ownership invalido em {table}")

    for child_table, column, parent_table in OWNERSHIP_PAIRS:
        mismatch = bind.execute(sa.text(
            f"SELECT 1 FROM {child_table} child "
            f"JOIN {parent_table} parent ON parent.id = child.{column} "
            f"WHERE child.{column} IS NOT NULL "
            "AND child.tenant_id <> parent.tenant_id LIMIT 1"
        )).scalar()
        if mismatch is not None:
            raise RuntimeError(
                "Agente WhatsApp: relacionamento entre empresas bloqueia a migracao "
                f"({child_table}.{column} -> {parent_table}.id)"
            )


def _require_no_scoped_duplicates(bind) -> None:
    for _name, table, columns, predicate in SCOPED_UNIQUES:
        where = f"WHERE {predicate}" if predicate else ""
        duplicate = bind.execute(sa.text(
            f"SELECT 1 FROM {table} {where} GROUP BY {columns} HAVING COUNT(*) > 1 LIMIT 1"
        )).scalar()
        if duplicate is not None:
            raise RuntimeError(
                f"Agente WhatsApp: chave tenant-scoped duplicada em {table} ({columns})"
            )


def upgrade() -> None:
    bind = op.get_bind()
    _require_valid_tenant_ownership(bind)
    _require_no_scoped_duplicates(bind)

    # Establish the tenant keys before removing the legacy global contracts.
    for name, table, columns, predicate in SCOPED_UNIQUES:
        where = f" WHERE {predicate}" if predicate else ""
        op.execute(sa.text(f"CREATE UNIQUE INDEX {name} ON {table} ({columns}){where}"))

    for table, constraint in GLOBAL_CONSTRAINTS:
        op.execute(sa.text(f'ALTER TABLE "{table}" DROP CONSTRAINT IF EXISTS "{constraint}"'))
    op.execute(sa.text("DROP INDEX IF EXISTS uq_agente_whatsapp_messages_idempotency_key"))

    for name, table, columns in PERFORMANCE_INDEXES:
        op.execute(sa.text(f"CREATE INDEX {name} ON {table} ({columns})"))


def downgrade() -> None:
    # Reintroducing global uniqueness could destroy valid multi-tenant data.
    # Retain the scoped keys and only remove non-unique performance indexes.
    for name, table, _columns in reversed(PERFORMANCE_INDEXES):
        op.drop_index(name, table_name=table)
