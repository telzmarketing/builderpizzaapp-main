from pathlib import Path

from backend.models.print_center import PrintAgentCredential, PrintAgentPairing
from backend.schemas.print_center import PrintAgentHeartbeatIn, PrintAgentJobStatusIn, PrintAgentPairIn
from backend.services.print_agent_service import PrintAgentReleaseService


ROOT = Path(__file__).parents[1]


def test_print_agent_protocol_is_registered_and_tenant_scoped():
    main = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")
    route = (ROOT / "backend" / "routes" / "print_agent.py").read_text(encoding="utf-8")
    migration = (ROOT / "backend" / "migrations" / "versions" / "20261122_print_agent_protocol.py").read_text(encoding="utf-8")
    assert "print_agent_routes.router" in main
    for path in ("/pair", "/jobs/next", "/jobs/{job_id}/status", "/heartbeat"):
        assert path in route
    assert "tenant_id" in migration
    assert "token_hash" in migration
    assert PrintAgentPairing.__table__.c.tenant_id is not None
    assert PrintAgentCredential.__table__.c.tenant_id is not None


def test_agent_payloads_are_strict_and_statuses_are_bounded():
    assert PrintAgentPairIn(code="a" * 16, hostname="GT-PC", agent_version="1.0.0").hostname == "GT-PC"
    assert PrintAgentHeartbeatIn(printers=[{"code": "kitchen", "status": "ready"}]).printers
    assert PrintAgentJobStatusIn(status="printed").status == "printed"


def test_release_is_fail_closed_when_artifact_is_not_configured(monkeypatch):
    monkeypatch.setenv("PRINT_AGENT_ARTIFACT_PATH", "")
    from backend.config import get_settings
    get_settings.cache_clear()
    try:
        metadata = PrintAgentReleaseService.metadata()
        assert metadata["available"] is False
        assert metadata["download_url"] is None
        assert PrintAgentReleaseService.artifact_path() is None
    finally:
        get_settings.cache_clear()
