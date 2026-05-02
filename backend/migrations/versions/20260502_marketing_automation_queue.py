"""marketing automation queue and audit

Revision ID: 20260502_marketing_automation_queue
Revises: 20260502_customer_ai_analysis_jobs
Create Date: 2026-05-02
"""
from __future__ import annotations

from alembic import op

revision = "20260502_marketing_automation_queue"
down_revision = "20260502_customer_ai_analysis_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE marketing_automations ADD COLUMN IF NOT EXISTS description TEXT")
    op.execute("ALTER TABLE marketing_automations ADD COLUMN IF NOT EXISTS conditions_json TEXT NOT NULL DEFAULT '[]'")
    op.execute("ALTER TABLE marketing_automations ADD COLUMN IF NOT EXISTS actions_json TEXT NOT NULL DEFAULT '[]'")
    op.execute("ALTER TABLE marketing_automations ADD COLUMN IF NOT EXISTS frequency VARCHAR(30) NOT NULL DEFAULT 'once'")
    op.execute("ALTER TABLE marketing_automations ADD COLUMN IF NOT EXISTS max_sends_per_customer INTEGER NOT NULL DEFAULT 1")
    op.execute("ALTER TABLE marketing_automations ADD COLUMN IF NOT EXISTS cooldown_hours INTEGER NOT NULL DEFAULT 24")
    op.execute("ALTER TABLE marketing_automations ADD COLUMN IF NOT EXISTS daily_limit INTEGER")
    op.execute("ALTER TABLE marketing_automations ADD COLUMN IF NOT EXISTS allowed_start_time VARCHAR(5)")
    op.execute("ALTER TABLE marketing_automations ADD COLUMN IF NOT EXISTS allowed_end_time VARCHAR(5)")
    op.execute("ALTER TABLE marketing_automations ADD COLUMN IF NOT EXISTS allowed_weekdays VARCHAR(30)")
    op.execute("ALTER TABLE marketing_automations ADD COLUMN IF NOT EXISTS priority INTEGER NOT NULL DEFAULT 100")
    op.execute("ALTER TABLE marketing_automations ADD COLUMN IF NOT EXISTS coupon_id VARCHAR REFERENCES coupons(id) ON DELETE SET NULL")
    op.execute("ALTER TABLE marketing_automations ADD COLUMN IF NOT EXISTS product_id VARCHAR REFERENCES products(id) ON DELETE SET NULL")
    op.execute("ALTER TABLE marketing_automations ADD COLUMN IF NOT EXISTS group_id VARCHAR")
    op.execute("ALTER TABLE marketing_automations ADD COLUMN IF NOT EXISTS segment_id VARCHAR REFERENCES customer_segments(id) ON DELETE SET NULL")
    op.execute("ALTER TABLE marketing_automations ADD COLUMN IF NOT EXISTS next_run_at TIMESTAMPTZ")
    op.execute("ALTER TABLE marketing_automations ADD COLUMN IF NOT EXISTS last_evaluated_at TIMESTAMPTZ")
    op.execute("ALTER TABLE marketing_automations ADD COLUMN IF NOT EXISTS created_by VARCHAR(200)")
    op.execute("ALTER TABLE marketing_automations ADD COLUMN IF NOT EXISTS updated_by VARCHAR(200)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_marketing_automations_next_run_at ON marketing_automations(next_run_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_marketing_automations_priority ON marketing_automations(priority)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS automation_conditions (
            id VARCHAR PRIMARY KEY,
            automation_id VARCHAR NOT NULL REFERENCES marketing_automations(id) ON DELETE CASCADE,
            condition_type VARCHAR(50) NOT NULL,
            field VARCHAR(100) NOT NULL,
            operator VARCHAR(40) NOT NULL,
            value_json TEXT NOT NULL DEFAULT '{}',
            sort_order INTEGER NOT NULL DEFAULT 0,
            active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_automation_conditions_automation_id ON automation_conditions(automation_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_automation_conditions_type ON automation_conditions(condition_type)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS automation_actions (
            id VARCHAR PRIMARY KEY,
            automation_id VARCHAR NOT NULL REFERENCES marketing_automations(id) ON DELETE CASCADE,
            action_type VARCHAR(50) NOT NULL DEFAULT 'send_message',
            channel VARCHAR(20),
            template_id VARCHAR,
            subject TEXT,
            message_body TEXT,
            coupon_id VARCHAR REFERENCES coupons(id) ON DELETE SET NULL,
            product_id VARCHAR REFERENCES products(id) ON DELETE SET NULL,
            config_json TEXT NOT NULL DEFAULT '{}',
            sort_order INTEGER NOT NULL DEFAULT 0,
            active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_automation_actions_automation_id ON automation_actions(automation_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_automation_actions_type ON automation_actions(action_type)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS automation_executions (
            id VARCHAR PRIMARY KEY,
            automation_id VARCHAR NOT NULL REFERENCES marketing_automations(id) ON DELETE CASCADE,
            customer_id VARCHAR REFERENCES customers(id) ON DELETE SET NULL,
            trigger_event_id VARCHAR REFERENCES customer_events(id) ON DELETE SET NULL,
            source_event_type VARCHAR(80),
            channel VARCHAR(20) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            scheduled_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            started_at TIMESTAMPTZ,
            sent_at TIMESTAMPTZ,
            finished_at TIMESTAMPTZ,
            next_attempt_at TIMESTAMPTZ,
            attempts INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 3,
            dedupe_key VARCHAR(300) NOT NULL,
            subject TEXT,
            message_body TEXT,
            provider_message_id VARCHAR(300),
            error TEXT,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT uq_automation_executions_dedupe_key UNIQUE (dedupe_key)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_automation_executions_automation_id ON automation_executions(automation_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_automation_executions_customer_id ON automation_executions(customer_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_automation_executions_status ON automation_executions(status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_automation_executions_scheduled_at ON automation_executions(scheduled_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_automation_executions_status_scheduled ON automation_executions(status, scheduled_at)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS automation_execution_logs (
            id VARCHAR PRIMARY KEY,
            execution_id VARCHAR REFERENCES automation_executions(id) ON DELETE CASCADE,
            automation_id VARCHAR REFERENCES marketing_automations(id) ON DELETE CASCADE,
            customer_id VARCHAR REFERENCES customers(id) ON DELETE SET NULL,
            status VARCHAR(20) NOT NULL,
            event_type VARCHAR(60) NOT NULL,
            message TEXT,
            error TEXT,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_automation_execution_logs_execution_id ON automation_execution_logs(execution_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_automation_execution_logs_automation_id ON automation_execution_logs(automation_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_automation_execution_logs_customer_id ON automation_execution_logs(customer_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_automation_execution_logs_created_at ON automation_execution_logs(created_at DESC)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS automation_audit_logs (
            id VARCHAR PRIMARY KEY,
            automation_id VARCHAR REFERENCES marketing_automations(id) ON DELETE CASCADE,
            action VARCHAR(60) NOT NULL,
            changed_by VARCHAR(200),
            before_json TEXT,
            after_json TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_automation_audit_logs_automation_id ON automation_audit_logs(automation_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_automation_audit_logs_created_at ON automation_audit_logs(created_at DESC)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS automation_audit_logs")
    op.execute("DROP TABLE IF EXISTS automation_execution_logs")
    op.execute("DROP TABLE IF EXISTS automation_executions")
    op.execute("DROP TABLE IF EXISTS automation_actions")
    op.execute("DROP TABLE IF EXISTS automation_conditions")
    op.execute("DROP INDEX IF EXISTS ix_marketing_automations_priority")
    op.execute("DROP INDEX IF EXISTS ix_marketing_automations_next_run_at")
    op.execute("ALTER TABLE marketing_automations DROP COLUMN IF EXISTS updated_by")
    op.execute("ALTER TABLE marketing_automations DROP COLUMN IF EXISTS created_by")
    op.execute("ALTER TABLE marketing_automations DROP COLUMN IF EXISTS last_evaluated_at")
    op.execute("ALTER TABLE marketing_automations DROP COLUMN IF EXISTS next_run_at")
    op.execute("ALTER TABLE marketing_automations DROP COLUMN IF EXISTS segment_id")
    op.execute("ALTER TABLE marketing_automations DROP COLUMN IF EXISTS group_id")
    op.execute("ALTER TABLE marketing_automations DROP COLUMN IF EXISTS product_id")
    op.execute("ALTER TABLE marketing_automations DROP COLUMN IF EXISTS coupon_id")
    op.execute("ALTER TABLE marketing_automations DROP COLUMN IF EXISTS priority")
    op.execute("ALTER TABLE marketing_automations DROP COLUMN IF EXISTS allowed_weekdays")
    op.execute("ALTER TABLE marketing_automations DROP COLUMN IF EXISTS allowed_end_time")
    op.execute("ALTER TABLE marketing_automations DROP COLUMN IF EXISTS allowed_start_time")
    op.execute("ALTER TABLE marketing_automations DROP COLUMN IF EXISTS daily_limit")
    op.execute("ALTER TABLE marketing_automations DROP COLUMN IF EXISTS cooldown_hours")
    op.execute("ALTER TABLE marketing_automations DROP COLUMN IF EXISTS max_sends_per_customer")
    op.execute("ALTER TABLE marketing_automations DROP COLUMN IF EXISTS frequency")
    op.execute("ALTER TABLE marketing_automations DROP COLUMN IF EXISTS actions_json")
    op.execute("ALTER TABLE marketing_automations DROP COLUMN IF EXISTS conditions_json")
    op.execute("ALTER TABLE marketing_automations DROP COLUMN IF EXISTS description")
