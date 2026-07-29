import ast
from pathlib import Path


SERVICE = (
    Path(__file__).parents[1]
    / "backend/services/agente_whatsapp_outbox_service.py"
)


def test_outbox_service_uses_trusted_legacy_job_context_by_default():
    source = SERVICE.read_text(encoding="utf-8")

    assert 'LEGACY_TENANT_ID = "tenant-legacy-default"' in source
    assert "tenant_context: TenantContext | None = None" in source
    assert "tenant_id=LEGACY_TENANT_ID" in source
    assert "source=TenantSource.JOB" in source
    assert "self._tenant_id = self._tenant_context.tenant_id" in source


def test_all_outbox_service_creates_assign_tenant_ownership():
    tree = ast.parse(SERVICE.read_text(encoding="utf-8"))
    tenant_owned_models = {
        "AgenteWhatsAppOutbox",
        "AgenteWhatsAppInternalAlert",
        "AgenteWhatsAppProviderState",
    }
    constructors = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in tenant_owned_models
    ]

    assert {node.func.id for node in constructors} == tenant_owned_models
    for constructor in constructors:
        tenant_keyword = next(
            (
                keyword
                for keyword in constructor.keywords
                if keyword.arg == "tenant_id"
            ),
            None,
        )
        assert tenant_keyword is not None, (
            f"{constructor.func.id} sem tenant_id na linha {constructor.lineno}"
        )
        assert isinstance(tenant_keyword.value, ast.Attribute)
        assert tenant_keyword.value.attr == "_tenant_id"


def test_provider_state_and_internal_alert_lookups_are_tenant_scoped():
    source = SERVICE.read_text(encoding="utf-8")

    assert (
        "AgenteWhatsAppProviderState.tenant_id == self._tenant_id"
        in source
    )
    assert (
        "AgenteWhatsAppInternalAlert.tenant_id == self._tenant_id"
        in source
    )
    assert "AgenteWhatsAppOutbox.tenant_id == self._tenant_id" in source
    assert "tenant_context=self._tenant_context" in source
