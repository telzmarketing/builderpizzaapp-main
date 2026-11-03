"""Capture contracts and a deterministic fake adapter.

The fake adapter intentionally returns bytes generated from the request key.
It is not a camera emulator and must not be used as evidence that physical
capture works.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class CaptureResult:
    """Result returned by a capture adapter."""

    payload: bytes
    content_type: str
    source: str
    sequence: int
    deterministic_key: str


class CaptureAdapter(Protocol):
    """Minimal contract a future local camera gateway can implement."""

    def capture(self, source: str, *, sequence: int = 0) -> CaptureResult:
        """Capture one frame from ``source`` without application side effects."""


class FakeCaptureAdapter:
    """Deterministic adapter for tests and local development only."""

    def __init__(self, *, namespace: str = "production-vision-fake") -> None:
        if not namespace:
            raise ValueError("namespace must not be empty")
        self.namespace = namespace

    def capture(self, source: str, *, sequence: int = 0) -> CaptureResult:
        if not source:
            raise ValueError("source must not be empty")
        if sequence < 0:
            raise ValueError("sequence must be non-negative")

        key = f"{self.namespace}\0{source}\0{sequence}"
        digest = hashlib.sha256(key.encode("utf-8")).digest()
        # A stable, non-image payload is intentional: callers must not mistake
        # this adapter for a physical camera or successful image processing.
        payload = b"PV-FAKE-FRAME\n" + digest
        return CaptureResult(
            payload=payload,
            content_type="application/octet-stream",
            source=source,
            sequence=sequence,
            deterministic_key=hashlib.sha256(key.encode("utf-8")).hexdigest(),
        )
