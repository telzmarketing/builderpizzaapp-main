"""Contract tests for the Wave 6 Email Marketing tenant boundary.

These assertions deliberately describe the security boundary instead of merely
checking that the ORM models expose a ``tenant_id`` field.  A shared SMTP
configuration or an automation worker that omits the tenant would still leak
data even with tenant-aware models.
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_email_marketing_routes_bind_a_trusted_panel_tenant_context():
    source = _source("backend/routes/email_marketing.py")

    assert "panel_wave6_context" in source
    assert "WAVE6_SESSION_TENANT_KEY" in source
    assert "wave6_tenant_id" in source
    assert "Depends(panel_wave6_context)" in source
    assert "block_unsafe_wave6_route" not in source


def test_email_models_and_all_administrative_resources_are_scoped_by_tenant():
    source = _source("backend/routes/email_marketing.py")

    for model in (
        "EmailTemplate",
        "EmailContactList",
        "EmailContactListItem",
        "EmailMessage",
        "EmailCampaign",
        "EmailConfig",
    ):
        model_start = source.index(f"class {model}(")
        next_class = source.find("\nclass ", model_start + 1)
        definition = source[model_start:next_class if next_class != -1 else None]
        assert "tenant_id = wave6_tenant_column" in definition, model

    for predicate in (
        "EmailTemplate.tenant_id == tenant_id",
        "EmailContactList.tenant_id == tenant_id",
        "EmailCampaign.tenant_id == tenant_id",
    ):
        assert predicate in source

    # Every persisted resource created by this module must inherit the trusted
    # request tenant, rather than accepting a caller-supplied tenant id.
    assert source.count("tenant_id=tenant_id") >= 5


def test_smtp_configuration_is_loaded_and_created_per_tenant():
    source = _source("backend/routes/email_marketing.py")

    assert "def _get_config(db: Session, tenant_id: str)" in source
    assert "EmailConfig.tenant_id == tenant_id" in source
    assert "EmailConfig(id=f\"email-config-{tenant_id}\", tenant_id=tenant_id)" in source
    assert "_get_config(db, tenant_id)" in source
    assert 'EmailConfig.id == "default"' not in source


def test_recipient_resolution_and_message_history_cannot_cross_tenants():
    source = _source("backend/routes/email_marketing.py")

    assert "def _resolve_recipients(" in source
    recipient_start = source.index("def _resolve_recipients(")
    recipient_end = source.index("\ndef _contact_list_to_dict", recipient_start)
    recipients = source[recipient_start:recipient_end]
    assert "tenant_id: str" in recipients
    assert recipients.count(":tenant_id") >= 4
    assert "i.tenant_id = :tenant_id" in recipients
    assert "l.tenant_id = :tenant_id" in recipients
    assert "c.tenant_id = :tenant_id" in recipients
    assert "cgm.tenant_id = :tenant_id" in recipients

    messages_start = source.index("def list_messages(")
    messages_end = source.index("\n\n#", messages_start)
    messages = source[messages_start:messages_end]
    assert "WHERE em.tenant_id = :tenant_id" in messages
    assert "c.tenant_id = em.tenant_id" in messages
    assert "et.tenant_id = em.tenant_id" in messages


def test_automation_workers_propagate_tenant_to_smtp_and_email_history():
    service = _source("backend/services/automation_service.py")
    legacy_routes = _source("backend/routes/automations.py")

    email_send_start = service.index("def send_message(")
    email_send_end = service.index("\ndef enqueue_automation", email_send_start)
    email_send = service[email_send_start:email_send_end]
    assert '_get_config(db, automation["tenant_id"])' in email_send

    log_start = service.index("def log_channel_message(")
    log_end = service.index("\ndef send_message", log_start)
    channel_log = service[log_start:log_end]
    assert "INSERT INTO email_messages" in channel_log
    assert "tenant_id, template_id" in channel_log
    assert '"tenant_id": automation["tenant_id"]' in channel_log

    # The old duplicate runner is unreachable, but must not remain as a
    # tempting global SMTP bypass for a future refactor.
    assert "cfg = _get_config(db)" not in legacy_routes
