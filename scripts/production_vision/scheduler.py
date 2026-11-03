"""Adaptive, hardware-independent capture scheduling."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CaptureSlot:
    sequence: int
    offset_seconds: float
    is_final: bool = False


class AdaptiveCaptureScheduler:
    """Plan five adaptive samples and a mandatory final capture.

    Samples are spread using increasing fractions so short sessions retain
    useful early coverage while long sessions leave more room between frames.
    The final slot is always exactly at ``duration_seconds``.
    """

    _fractions = (0.0, 0.20, 0.45, 0.70, 0.90)

    def __init__(self, *, sample_count: int = 5, minimum_duration: float = 1.0) -> None:
        if sample_count != 5:
            raise ValueError("the local contract requires exactly five samples")
        if minimum_duration <= 0:
            raise ValueError("minimum_duration must be positive")
        self.sample_count = sample_count
        self.minimum_duration = minimum_duration

    def plan(self, duration_seconds: float) -> tuple[CaptureSlot, ...]:
        if duration_seconds < 0:
            raise ValueError("duration_seconds must be non-negative")
        duration = max(float(duration_seconds), self.minimum_duration)
        samples = tuple(
            CaptureSlot(sequence=index + 1, offset_seconds=round(duration * fraction, 6))
            for index, fraction in enumerate(self._fractions)
        )
        final = CaptureSlot(sequence=self.sample_count + 1, offset_seconds=round(duration, 6), is_final=True)
        return samples + (final,)
