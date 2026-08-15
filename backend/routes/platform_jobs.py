"""Master Central queue and worker observability endpoints."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.core.platform_authorization import require_platform_permission
from backend.database import get_db
from backend.models.admin import AdminUser
from backend.routes.platform_tenants import _success
from backend.schemas.platform_master import ApiEnvelope
from backend.schemas.platform_operations import JobPageOut, JobsOverviewOut, QueueListOut
from backend.services.platform_jobs_service import PlatformJobsService

router = APIRouter(prefix="/admin/platform/jobs", tags=["platform-jobs"])


@router.get("/overview", response_model=ApiEnvelope[JobsOverviewOut])
def jobs_overview(
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(require_platform_permission("jobs.view")),
):
    return _success(PlatformJobsService(db).overview())


@router.get("/queues", response_model=ApiEnvelope[QueueListOut])
def job_queues(
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(require_platform_permission("jobs.view")),
):
    return _success(PlatformJobsService(db).queues())


@router.get("/items", response_model=ApiEnvelope[JobPageOut])
def job_items(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    tenant_id: str | None = Query(default=None, max_length=100),
    queue: str | None = Query(default=None, max_length=80),
    status: str | None = Query(default=None, pattern="^(queued|running|retrying|succeeded|failed|dead|cancelled|unknown)$"),
    age_minutes: int | None = Query(default=None, ge=0, le=525600),
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(require_platform_permission("jobs.view")),
):
    return _success(PlatformJobsService(db).list_items(
        page=page, page_size=page_size, tenant_id=tenant_id,
        queue_key=queue, status=status, age_minutes=age_minutes,
    ))
