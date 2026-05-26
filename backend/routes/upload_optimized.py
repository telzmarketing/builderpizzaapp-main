from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse


router = APIRouter(prefix="/uploads", tags=["uploads"])

_CACHE_HEADERS = {"Cache-Control": "public, max-age=31536000, immutable"}
_OPTIMIZABLE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
_PASSTHROUGH_EXTENSIONS = _OPTIMIZABLE_EXTENSIONS | {".gif", ".svg", ".avif"}


def _safe_upload_path(path: str) -> Path:
    clean = path.replace("\\", "/").lstrip("/")
    if not clean or ".." in clean.split("/"):
        raise HTTPException(status_code=404, detail="Arquivo nao encontrado.")
    source = Path("uploads", clean).resolve()
    uploads_root = Path("uploads").resolve()
    if uploads_root not in source.parents and source != uploads_root:
        raise HTTPException(status_code=404, detail="Arquivo nao encontrado.")
    if not source.is_file():
        raise HTTPException(status_code=404, detail="Arquivo nao encontrado.")
    return source


def _optimized_path(source: Path, width: int) -> Path:
    stat = source.stat()
    safe_name = "__".join(source.relative_to(Path("uploads").resolve()).parts)
    stem = Path(safe_name).stem
    return Path(
        "uploads",
        ".optimized",
        f"w{width}",
        f"{stem}-{int(stat.st_mtime)}-{stat.st_size}.webp",
    )


def _build_webp(source: Path, target: Path, width: int) -> bool:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False

    target.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(source),
        "-vf",
        f"scale='min({width},iw)':-2",
        "-c:v",
        "libwebp",
        "-quality",
        "74",
        "-compression_level",
        "6",
        str(target),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, timeout=30)
    except (subprocess.SubprocessError, OSError):
        return False
    return target.is_file() and target.stat().st_size > 0 and target.stat().st_size < source.stat().st_size


def _file_response(path: Path, media_type: str | None = None) -> FileResponse:
    return FileResponse(path, media_type=media_type, headers=_CACHE_HEADERS)


@router.get("/optimized/{width}/{path:path}")
def optimized_upload(width: int, path: str):
    width = max(64, min(width, 1280))
    source = _safe_upload_path(path)
    extension = source.suffix.lower()

    if extension not in _PASSTHROUGH_EXTENSIONS:
        raise HTTPException(status_code=404, detail="Arquivo nao encontrado.")

    if extension not in _OPTIMIZABLE_EXTENSIONS:
        return _file_response(source)

    target = _optimized_path(source, width)
    if target.is_file() or _build_webp(source, target, width):
        return _file_response(target, media_type="image/webp")

    return _file_response(source)
