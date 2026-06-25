import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.database import get_db
from backend.routes.admin_auth import get_current_admin
from backend.core.response import ok

router = APIRouter(tags=["site-config"])

_IMAGE_EXTENSIONS = (".apng", ".avif", ".gif", ".ico", ".jpeg", ".jpg", ".jfif", ".pjpeg", ".pjp", ".png", ".svg", ".webp")


def _get_content(db: Session) -> dict:
    row = db.execute(text("SELECT content FROM site_config WHERE id = 'default'")).fetchone()
    if row and row[0]:
        try:
            return json.loads(row[0])
        except Exception:
            pass
    return {}


def _get_content_with_updated_at(db: Session) -> tuple[dict[str, Any], datetime | None]:
    row = db.execute(text("SELECT content, updated_at FROM site_config WHERE id = 'default'")).fetchone()
    if not row:
        return {}, None
    content: dict[str, Any] = {}
    if row[0]:
        try:
            loaded = json.loads(row[0])
            if isinstance(loaded, dict):
                content = loaded
        except Exception:
            content = {}
    return content, row[1]


def _asset_url(value: Any) -> str:
    raw = str(value or "").strip().replace("\\", "/")
    if not raw:
        return ""
    lower = raw.lower()
    if raw.startswith("data:"):
        return ""
    if raw.startswith(("http://", "https://")) and lower.endswith(_IMAGE_EXTENSIONS):
        return raw
    if raw.startswith("/") and lower.endswith(_IMAGE_EXTENSIONS):
        return raw
    if raw.startswith(("uploads/", "api/uploads/")) and lower.endswith(_IMAGE_EXTENSIONS):
        return f"/{raw}"
    if lower.endswith(_IMAGE_EXTENSIONS):
        return f"/uploads/{raw}"
    return ""


def _default_favicon(size: int) -> str:
    if size <= 64:
        return "/icons/favicon-moschettieri-32.png"
    if size >= 512:
        return "/icons/icon-512.png"
    return "/icons/icon-192.png"


def _brand(content: dict[str, Any]) -> dict[str, Any]:
    brand = content.get("brand")
    return brand if isinstance(brand, dict) else {}


def _favicon_url(content: dict[str, Any], size: int) -> str:
    return _asset_url(_brand(content).get("faviconUrl")) or _default_favicon(size)


def _version(updated_at: datetime | None) -> str:
    return str(int(updated_at.timestamp())) if updated_at else "default"


@router.get("/site-config")
def get_site_config(db: Session = Depends(get_db)):
    return ok(_get_content(db))


@router.get("/site-config/favicon", include_in_schema=False)
def get_global_favicon(
    size: int = Query(default=192, ge=16, le=1024),
    db: Session = Depends(get_db),
):
    content, updated_at = _get_content_with_updated_at(db)
    target = _favicon_url(content, size)
    separator = "&" if "?" in target else "?"
    if target.startswith("/"):
        target = f"{target}{separator}v={_version(updated_at)}"
    return RedirectResponse(
        url=target,
        status_code=307,
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


@router.get("/site-config/manifest.webmanifest", include_in_schema=False)
def get_global_manifest(db: Session = Depends(get_db)):
    content, updated_at = _get_content_with_updated_at(db)
    brand = _brand(content)
    name = str(brand.get("pageTitle") or brand.get("name") or "Del Basito by Moschettieri").strip()
    short_name = str(brand.get("name") or "Moschettieri").strip()
    version = _version(updated_at)
    return JSONResponse(
        {
            "name": name,
            "short_name": short_name[:24] or "Moschettieri",
            "description": "Delivery Moschettieri",
            "start_url": "/motoboy",
            "scope": "/motoboy",
            "display": "standalone",
            "display_override": ["fullscreen", "standalone"],
            "orientation": "portrait",
            "theme_color": "#000000",
            "background_color": "#000000",
            "icons": [
                {
                    "src": f"/api/site-config/favicon?size=192&v={version}",
                    "sizes": "192x192",
                    "purpose": "any maskable",
                },
                {
                    "src": f"/api/site-config/favicon?size=512&v={version}",
                    "sizes": "512x512",
                    "purpose": "any maskable",
                },
            ],
        },
        media_type="application/manifest+json",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


@router.put("/admin/site-config")
def update_site_config(
    body: dict,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    content = json.dumps(body, ensure_ascii=False)
    db.execute(text(
        "INSERT INTO site_config (id, content, updated_at) VALUES ('default', :c, NOW()) "
        "ON CONFLICT (id) DO UPDATE SET content = EXCLUDED.content, updated_at = NOW()"
    ), {"c": content})
    db.commit()
    return ok(body)
