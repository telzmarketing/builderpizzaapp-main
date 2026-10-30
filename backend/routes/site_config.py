from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.routes.admin_auth import get_current_admin
from backend.core.response import ok
from backend.schemas.site_config import SiteConfigIn
from backend.services.site_config_service import SiteConfigService

router = APIRouter(tags=["site-config"])
_NO_CACHE = {"Cache-Control": "no-cache, no-store, must-revalidate"}


@router.get("/site-config")
def get_site_config(request: Request, db: Session = Depends(get_db)):
    content, _, _ = SiteConfigService(db).read(request)
    response = ok(content)
    response.headers.update(_NO_CACHE)
    return response


@router.get("/site-config/favicon", include_in_schema=False)
def get_global_favicon(
    request: Request,
    size: int = Query(default=192, ge=16, le=1024),
    db: Session = Depends(get_db),
):
    return RedirectResponse(
        url=SiteConfigService(db).favicon_target(request, size),
        status_code=307, headers=_NO_CACHE,
    )


@router.get("/site-config/manifest.webmanifest", include_in_schema=False)
def get_global_manifest(request: Request, app: str | None = Query(default=None), db: Session = Depends(get_db)):
    return JSONResponse(
        SiteConfigService(db).manifest(request, app=app),
        media_type="application/manifest+json", headers=_NO_CACHE,
    )


@router.put("/admin/site-config")
def update_site_config(
    body: SiteConfigIn, request: Request,
    db: Session = Depends(get_db), admin=Depends(get_current_admin),
):
    return ok(SiteConfigService(db).save(request, admin, body.root))


@router.get("/admin/site-config")
def get_admin_site_config(request: Request, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    response = ok(SiteConfigService(db).read_admin(request, admin))
    response.headers.update(_NO_CACHE)
    return response
