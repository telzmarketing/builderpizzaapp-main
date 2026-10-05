"""Contracts for tenant-owned background execution.

The project has no Celery/RQ/APScheduler consumer.  These checks protect the
two real deferred entry points: Starlette CRM tasks and the WhatsApp runtime
worker/callback path.
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_crm_background_task_carries_server_resolved_job_metadata() -> None:
    route = _read("backend/routes/crm.py")
    service = _read("backend/services/customer_ai_service.py")

    assert "job_metadata(context)" in route
    assert "run_customer_ai_analysis_job, job[\"id\"], job_metadata(context)" in route
    assert "context_from_job_metadata(metadata)" in service
    assert "context.assert_tenant(job.tenant_id)" in service
    assert "bind_tenant_context(context)" in service
    assert "Job de analise CRM sem metadata de tenant." in service


def test_whatsapp_worker_iterates_persisted_tenants_and_binds_job_context() -> None:
    worker = _read("backend/services/agente_whatsapp_worker.py")

    assert "def _active_tenant_ids" in worker
    assert "Tenant.status == \"active\"" in worker
    assert "trusted_process_context(tenant_id, source=TenantSource.JOB)" in worker
    assert "bind_wave6_tenant_context(db, context)" in worker
    assert "for tenant_id in _active_tenant_ids(db)" in worker


def test_runtime_callback_uses_persisted_instance_tenant_not_provider_payload() -> None:
    gateway = _read("backend/services/whatsapp_gateway_service.py")
    driver = _read("backend/services/delivery_driver_whatsapp_service.py")

    assert 'trusted_payload["_trusted_tenant_id"] = instance.tenant_id' in gateway
    assert "Evento runtime sem instancia tenant confiavel." in gateway
    assert "process_driver_reply(trusted_payload)" in gateway
    assert 'payload.get("_trusted_tenant_id")' in driver
    assert "DeliveryPerson.tenant_id == tenant_id" in driver
    assert "tenant_context_missing" in driver


def test_global_platform_jobs_are_explicitly_excluded_from_tenant_work_contract() -> None:
    jobs = _read("backend/services/platform_jobs_service.py")
    worker = _read("backend/services/agente_whatsapp_worker.py")

    # Heartbeats describe a process/queue, while tenant iteration occurs in the
    # worker before it touches tenant-owned rows.
    assert "def record_heartbeat" in jobs
    assert "PlatformJobsService(heartbeat_db).record_heartbeat" in worker
