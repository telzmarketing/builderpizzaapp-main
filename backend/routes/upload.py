"""
Admin image upload endpoint.

Routes
------
POST /admin/upload — upload an image file; returns a permanent /uploads/<filename> URL.
"""
from __future__ import annotations

import os
from uuid import uuid4

from fastapi import APIRouter, Depends, File, UploadFile

from backend.core.response import ok, err_msg
from backend.routes.admin_auth import get_current_admin
from backend.models.admin import AdminUser

router = APIRouter(prefix="/admin", tags=["admin-upload"])

_ALLOWED_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/svg+xml",
}
_MAX_BYTES = 5 * 1024 * 1024  # 5 MB

_EXT_MAP = {
    "image/jpeg":   "jpg",
    "image/png":    "png",
    "image/gif":    "gif",
    "image/webp":   "webp",
    "image/svg+xml": "svg",
}


@router.post("/upload", response_model=None)
async def upload_image(
    file: UploadFile = File(...),
    _admin: AdminUser = Depends(get_current_admin),
):
    """
    Upload an image and save it permanently under the project-root ``uploads/`` directory.

    - Accepts: jpeg, png, gif, webp, svg+xml
    - Maximum file size: 5 MB
    - Returns: ``{ "url": "/uploads/<uuid>.<ext>" }``
    """
    # ── Content-type validation ───────────────────────────────────────────────
    content_type = (file.content_type or "").lower()
    if content_type not in _ALLOWED_TYPES:
        return err_msg(
            "Tipo de arquivo não permitido. Use JPEG, PNG, GIF, WebP ou SVG.",
            code="InvalidFileType",
            status_code=400,
        )

    # ── Read + size validation ────────────────────────────────────────────────
    data = await file.read()
    if len(data) > _MAX_BYTES:
        return err_msg(
            "Arquivo muito grande. O tamanho máximo permitido é 5 MB.",
            code="FileTooLarge",
            status_code=400,
        )

    # ── Ensure uploads directory exists ──────────────────────────────────────
    os.makedirs("uploads", exist_ok=True)

    # ── Write to disk ─────────────────────────────────────────────────────────
    ext = _EXT_MAP.get(content_type, "bin")
    filename = f"{uuid4().hex}.{ext}"
    dest = os.path.join("uploads", filename)

    with open(dest, "wb") as fh:
        fh.write(data)

    return ok({"url": f"/uploads/{filename}"})
