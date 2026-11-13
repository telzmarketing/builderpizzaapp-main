import pytest

from backend.services.agente_whatsapp_audio_service import (
    detect_audio_mime,
    resolve_audio_mime,
)


def test_octet_stream_ogg_is_normalized_from_magic_bytes():
    data = b"OggS" + b"\x00" * 32

    assert resolve_audio_mime(data, "application/octet-stream", "voice.bin") == "audio/ogg"
    assert detect_audio_mime(data) == "audio/ogg"


def test_octet_stream_uses_extension_only_when_content_matches():
    data = b"RIFF" + b"\x00" * 4 + b"WAVE" + b"\x00" * 16

    assert resolve_audio_mime(data, "application/octet-stream", "voice.wav") == "audio/wav"


@pytest.mark.parametrize("data", [b"not audio", b"", b"OggX" + b"\x00" * 16])
def test_octet_stream_invalid_content_is_rejected(data):
    with pytest.raises(ValueError, match="formato de audio nao identificado"):
        resolve_audio_mime(data, "application/octet-stream", "voice.ogg")


def test_declared_mime_with_parameters_is_normalized():
    data = b"OggS" + b"\x00" * 32

    assert resolve_audio_mime(data, "audio/ogg; codecs=opus", "voice.ogg") == "audio/ogg"


def test_declared_container_mime_cannot_bypass_signature_validation():
    with pytest.raises(ValueError, match="nao corresponde ao MIME declarado"):
        resolve_audio_mime(b"not an ogg file", "audio/ogg", "voice.ogg")
