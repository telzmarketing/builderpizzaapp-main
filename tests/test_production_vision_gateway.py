from io import BytesIO

import pytest

from scripts.production_vision import (
    AdaptiveCaptureScheduler,
    CameraUrlError,
    FakeCaptureAdapter,
    process_image,
    validate_camera_url,
)


def test_fake_adapter_is_deterministic_and_sequence_sensitive():
    adapter = FakeCaptureAdapter(namespace="test")
    first = adapter.capture("camera-a", sequence=1)
    same = adapter.capture("camera-a", sequence=1)
    other = adapter.capture("camera-a", sequence=2)

    assert first == same
    assert first.payload != other.payload
    assert first.content_type == "application/octet-stream"


@pytest.mark.parametrize("url", [
    "file:///etc/passwd",
    "ftp://camera.example/snapshot",
    "http://127.0.0.1/snapshot",
    "http://[::1]/snapshot",
    "http://10.0.0.4/snapshot",
    "http://user:secret@camera.example/snapshot",
])
def test_camera_url_rejects_unsafe_targets(url):
    with pytest.raises(CameraUrlError):
        validate_camera_url(url)


def test_camera_url_allows_public_https_url(monkeypatch):
    monkeypatch.setattr(
        "scripts.production_vision.ssrf._resolved_addresses",
        lambda hostname, port: {__import__("ipaddress").ip_address("8.8.8.8")},
    )
    assert validate_camera_url("https://camera.example/snapshot") == "https://camera.example/snapshot"


def test_private_camera_url_can_be_explicitly_allowed():
    assert validate_camera_url("http://192.168.1.20/snapshot", allow_private=True)


def test_scheduler_has_five_samples_and_mandatory_final_capture():
    slots = AdaptiveCaptureScheduler().plan(100)
    assert len(slots) == 6
    assert [slot.sequence for slot in slots] == [1, 2, 3, 4, 5, 6]
    assert slots[-1].is_final is True
    assert slots[-1].offset_seconds == 100
    assert all(left.offset_seconds <= right.offset_seconds for left, right in zip(slots, slots[1:]))


def test_scheduler_adapts_short_sessions_without_negative_or_duplicate_final_time():
    slots = AdaptiveCaptureScheduler().plan(0)
    assert slots[-1].offset_seconds == 1
    assert slots[-1].is_final is True


def test_image_processing_resizes_to_1280_when_pillow_is_available():
    pillow = pytest.importorskip("PIL")
    from PIL import Image

    source = Image.new("RGB", (2560, 1280), color="red")
    raw = BytesIO()
    source.save(raw, format="PNG")
    result = process_image(raw.getvalue())

    assert result.processed is True
    assert (result.width, result.height) == (1280, 640)
    with Image.open(BytesIO(result.payload)) as resized:
        assert resized.size == (1280, 640)


def test_invalid_image_is_preserved_without_fake_processing():
    raw = b"not-an-image"
    result = process_image(raw)
    assert result.payload == raw
    assert result.processed is False
    assert result.reason is not None
