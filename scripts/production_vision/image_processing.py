"""Optional, deterministic image normalization with Pillow."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO


@dataclass(frozen=True)
class ImageProcessingResult:
    payload: bytes
    processed: bool
    width: int | None
    height: int | None
    reason: str | None = None


def process_image(payload: bytes, *, max_width: int = 1280) -> ImageProcessingResult:
    """Resize a valid image to at most ``max_width`` while preserving ratio.

    Pillow is optional.  Invalid or unsupported data is returned unchanged;
    callers can persist the original and inspect ``processed``/``reason``.
    No inference, detection, cropping, or synthetic image generation occurs.
    """

    if not payload:
        raise ValueError("payload must not be empty")
    if max_width < 1:
        raise ValueError("max_width must be positive")
    try:
        from PIL import Image, ImageOps
    except ImportError:
        return ImageProcessingResult(payload, False, None, None, "pillow-unavailable")

    try:
        with Image.open(BytesIO(payload)) as image:
            image = ImageOps.exif_transpose(image)
            original_format = image.format or "PNG"
            width, height = image.size
            if width <= max_width:
                return ImageProcessingResult(payload, False, width, height, "within-limit")
            new_height = max(1, round(height * max_width / width))
            resized = image.resize((max_width, new_height), Image.Resampling.LANCZOS)
            output = BytesIO()
            save_format = original_format if original_format in {"PNG", "JPEG", "WEBP"} else "PNG"
            if save_format == "JPEG" and resized.mode not in {"RGB", "L"}:
                resized = resized.convert("RGB")
            resized.save(output, format=save_format)
            return ImageProcessingResult(output.getvalue(), True, max_width, new_height)
    except Exception as exc:  # Pillow uses several format-specific exception types.
        return ImageProcessingResult(payload, False, None, None, f"invalid-image:{type(exc).__name__}")
