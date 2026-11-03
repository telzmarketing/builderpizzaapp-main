"""Local, hardware-independent Production Vision building blocks.

This package deliberately does not connect to the application backend, KDS, or
physical cameras.  It is suitable for deterministic local tests and future
gateway integration.
"""

from .capture import CaptureAdapter, CaptureResult, FakeCaptureAdapter
from .image_processing import ImageProcessingResult, process_image
from .scheduler import CaptureSlot, AdaptiveCaptureScheduler
from .ssrf import CameraUrlError, validate_camera_url

__all__ = [
    "AdaptiveCaptureScheduler",
    "CameraUrlError",
    "CaptureAdapter",
    "CaptureResult",
    "CaptureSlot",
    "FakeCaptureAdapter",
    "ImageProcessingResult",
    "process_image",
    "validate_camera_url",
]
