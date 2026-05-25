from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass


VIDEO_TYPES = {
    "video/mp4",
    "video/webm",
    "video/quicktime",
}


@dataclass(frozen=True)
class MediaCompressionResult:
    data: bytes
    content_type: str
    extension: str
    compressed: bool = False


def compress_uploaded_media(data: bytes, content_type: str, extension: str) -> MediaCompressionResult:
    if content_type not in VIDEO_TYPES:
        return MediaCompressionResult(data=data, content_type=content_type, extension=extension)

    return _compress_video(data, content_type, extension)


def _compress_video(data: bytes, content_type: str, extension: str) -> MediaCompressionResult:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return MediaCompressionResult(data=data, content_type=content_type, extension=extension)

    suffix = f".{extension.lstrip('.') or 'bin'}"
    with tempfile.TemporaryDirectory() as tmpdir:
        source_path = os.path.join(tmpdir, f"source{suffix}")
        output_path = os.path.join(tmpdir, "compressed.mp4")

        with open(source_path, "wb") as source_file:
            source_file.write(data)

        command = [
            ffmpeg,
            "-y",
            "-i",
            source_path,
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "28",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            output_path,
        ]

        try:
            subprocess.run(command, check=True, capture_output=True, timeout=120)
        except (subprocess.SubprocessError, OSError):
            return MediaCompressionResult(data=data, content_type=content_type, extension=extension)

        if not os.path.exists(output_path):
            return MediaCompressionResult(data=data, content_type=content_type, extension=extension)

        with open(output_path, "rb") as output_file:
            compressed_data = output_file.read()

    if not compressed_data or len(compressed_data) >= len(data):
        return MediaCompressionResult(data=data, content_type=content_type, extension=extension)

    return MediaCompressionResult(
        data=compressed_data,
        content_type="video/mp4",
        extension="mp4",
        compressed=True,
    )
