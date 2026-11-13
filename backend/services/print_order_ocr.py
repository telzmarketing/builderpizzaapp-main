"""Optional local OCR adapter for Print Pedido.

This module is deliberately optional: it never calls a remote provider and
never fabricates text. If the local Tesseract stack is unavailable, callers
must keep the deterministic/manual review path.
"""
from __future__ import annotations

import io
from dataclasses import dataclass


@dataclass(frozen=True)
class LocalOcrResult:
    text: str
    provider: str = "tesseract-local"


def extract_local_text(data: bytes, content_type: str) -> LocalOcrResult | None:
    """Return OCR text only when an already-installed local stack is usable."""
    if not content_type.startswith("image/"):
        return None
    try:
        from PIL import Image
        import pytesseract
    except (ImportError, ModuleNotFoundError):
        return None

    try:
        with Image.open(io.BytesIO(data)) as image:
            text = pytesseract.image_to_string(image, lang="por+eng")
    except Exception:
        # OCR is an enhancement, never a reason to reject or lose a capture.
        return None
    text = (text or "").strip()
    return LocalOcrResult(text=text) if text else None
