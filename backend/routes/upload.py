"""
Admin image upload endpoint.

Routes
------
POST /admin/upload — upload an image file; returns a permanent /uploads/<filename> URL.
"""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Request, UploadFile
from sqlalchemy.orm import Session

from backend.core.response import ok, err_msg
from backend.routes.admin_auth import get_current_admin
from backend.models.admin import AdminUser
from backend.services.media_compression_service import compress_uploaded_media
from backend.config import get_settings
from backend.core.tenant_execution import tenant_upload_path
from backend.core.tenant_context import TenantContextMissing
from backend.core.tenant_runtime import resolve_panel_tenant_context
from backend.database import get_db

router = APIRouter(prefix="/admin", tags=["admin-upload"])

_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
}
_VIDEO_TYPES = {
    "video/mp4",
    "video/webm",
    "video/quicktime",
}
_AUDIO_TYPES = {
    "audio/ogg",
    "audio/opus",
    "audio/mpeg",
    "audio/mp4",
    "audio/webm",
}
_ALLOWED_TYPES = _IMAGE_TYPES | _VIDEO_TYPES | _AUDIO_TYPES

_MAX_IMAGE_BYTES = 5 * 1024 * 1024   # 5 MB
_MAX_VIDEO_BYTES = 50 * 1024 * 1024  # 50 MB
_MAX_AUDIO_BYTES = 20 * 1024 * 1024  # 20 MB

_EXT_MAP = {
    "image/jpeg":     "jpg",
    "image/png":      "png",
    "image/gif":      "gif",
    "image/webp":     "webp",
    "video/mp4":      "mp4",
    "video/webm":     "webm",
    "video/quicktime": "mov",
    "audio/ogg":      "ogg",
    "audio/opus":     "opus",
    "audio/mpeg":     "mp3",
    "audio/mp4":      "m4a",
    "audio/webm":     "webm",
}


@router.post("/upload", response_model=None)
async def upload_image(
    request: Request,
    file: UploadFile = File(...),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Upload an image and save it permanently under the project-root ``uploads/`` directory.

    - Accepts: jpeg, png, gif, webp, mp4, webm, mov, ogg, opus, mp3, m4a
    - Maximum file size: 5 MB for images, 50 MB for videos, 20 MB for audio
    - Returns: ``{ "url": "/uploads/<uuid>.<ext>" }``
    """
    # ── Content-type validation ───────────────────────────────────────────────
    content_type = (file.content_type or "").lower()
    if content_type not in _ALLOWED_TYPES:
        return err_msg(
            "Tipo de arquivo nao permitido. Use JPEG, PNG, GIF ou WebP para imagens, MP4, WebM, MOV para videos, ou OGG, OPUS, MP3, M4A para audio.",
            code="InvalidFileType",
            status_code=400,
        )

    # ── Read + size validation ────────────────────────────────────────────────
    data = await file.read()
    is_video = content_type in _VIDEO_TYPES
    is_audio = content_type in _AUDIO_TYPES
    max_bytes = _MAX_AUDIO_BYTES if is_audio else _MAX_VIDEO_BYTES if is_video else _MAX_IMAGE_BYTES
    if len(data) > max_bytes:
        limit_label = "20 MB" if is_audio else "50 MB" if is_video else "5 MB"
        return err_msg(
            f"Arquivo muito grande. O tamanho máximo permitido é {limit_label}.",
            code="FileTooLarge",
            status_code=413,
        )

    # ── Ensure uploads directory exists ──────────────────────────────────────
    # ── Write to disk ─────────────────────────────────────────────────────────
    ext = _EXT_MAP.get(content_type, "bin")
    media = compress_uploaded_media(data, content_type, ext)
    data = media.data
    ext = media.extension
    filename = f"{uuid4().hex}.{ext}"
    upload_root = Path("uploads")
    if get_settings().TENANT_UPLOAD_NAMESPACE_ENABLED:
        context = resolve_panel_tenant_context(request, db, admin)
        if context is None:
            raise TenantContextMissing("Upload tenantizado exige autenticacao multiempresa ativa.")
        dest_path = tenant_upload_path(upload_root, context, filename)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        url = f"/uploads/{context.tenant_id}/{filename}"
    else:
        # Exact legacy layout remains active while the rollout flag is off.
        upload_root.mkdir(parents=True, exist_ok=True)
        dest_path = upload_root / filename
        url = f"/uploads/{filename}"

    with open(dest_path, "wb") as fh:
        fh.write(data)

    return ok({"url": url})
