from pathlib import Path

from backend.models.label import PreparationLabelPrintJob


def test_preparation_label_job_is_execution_scoped_and_idempotent():
    assert PreparationLabelPrintJob.__table__.c.execution_id.nullable is False
    assert any(
        constraint.name == "uq_preparation_label_jobs_idempotency"
        for constraint in PreparationLabelPrintJob.__table__.constraints
    )
    migration = Path("backend/migrations/versions/20261026_preparation_label_jobs.py").read_text(encoding="utf-8")
    assert "preparation_executions.tenant_id" in migration
    assert "preparation_executions.id" in migration
    assert "preparation_label_print_jobs" in migration
