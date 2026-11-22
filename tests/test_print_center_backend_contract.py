from pathlib import Path

from backend.models.print_center import PrintJob, PrintJobEvent, PrintPrinter, PrintRoutingRule, PrintStation
from backend.schemas.print_center import PrintJobIn
from backend.services.print_center_service import PrintCenterService


ROOT = Path(__file__).parents[1]


def test_print_center_is_registered_in_backend_layers():
    env = (ROOT / "backend" / "migrations" / "env.py").read_text(encoding="utf-8")
    database = (ROOT / "backend" / "database.py").read_text(encoding="utf-8")
    main = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")
    migration = (ROOT / "backend" / "migrations" / "versions" / "20261121_print_center.py").read_text(encoding="utf-8")
    assert "print_center" in env and "print_center" in database and "print_center_routes.router" in main
    for table in ("print_stations", "print_printers", "print_routing_rules", "print_jobs", "print_job_events"):
        assert table in migration


def test_print_center_models_are_tenant_scoped_and_queue_is_idempotent():
    for model in (PrintStation, PrintPrinter, PrintRoutingRule, PrintJob, PrintJobEvent):
        assert "tenant_id" in model.__table__.columns
    constraints = {c.name for c in PrintJob.__table__.constraints if c.name}
    assert "uq_print_jobs_tenant_idempotency" in constraints
    body = PrintJobIn(
        external_job_id="GT-1", printer_id="printer-1", sector="expedicao",
        document_type="pizza_label", document_format="zpl", payload_ref="/api/print/jobs/GT-1/document",
    )
    assert body.copies == 1


def test_print_center_service_contains_no_external_credentials_or_command_execution():
    source = (ROOT / "backend" / "services" / "print_center_service.py").read_text(encoding="utf-8")
    assert "subprocess" not in source
    assert "password" not in source.lower()
    assert "tenant_id" in source
