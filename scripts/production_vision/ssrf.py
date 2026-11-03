"""SSRF-safe validation for camera snapshot URLs."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import SplitResult, urlsplit


class CameraUrlError(ValueError):
    """Raised when a camera URL is unsafe or malformed."""


def _resolved_addresses(hostname: str, port: int) -> set[ipaddress._BaseAddress]:
    try:
        infos = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except (socket.gaierror, OSError) as exc:
        raise CameraUrlError("camera hostname could not be resolved") from exc

    addresses: set[ipaddress._BaseAddress] = set()
    for info in infos:
        try:
            addresses.add(ipaddress.ip_address(info[4][0]))
        except (ValueError, IndexError):
            raise CameraUrlError("camera hostname returned an invalid address")
    return addresses


def validate_camera_url(url: str, *, allow_private: bool = False) -> str:
    """Validate and normalize an HTTP(S) camera URL.

    By default, loopback, private, link-local, multicast, reserved and
    unspecified destinations are rejected.  ``allow_private`` exists for a
    future gateway running inside a controlled LAN; it still rejects loopback,
    link-local, multicast and unspecified addresses.
    """

    if not isinstance(url, str) or not url.strip():
        raise CameraUrlError("camera URL is required")
    parsed: SplitResult = urlsplit(url.strip())
    if parsed.scheme.lower() not in {"http", "https"}:
        raise CameraUrlError("camera URL must use http or https")
    if not parsed.hostname or parsed.username is not None or parsed.password is not None:
        raise CameraUrlError("camera URL must contain a hostname without credentials")
    if parsed.fragment:
        raise CameraUrlError("camera URL must not contain a fragment")
    try:
        port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    except ValueError as exc:
        raise CameraUrlError("camera URL has an invalid port") from exc
    if not 1 <= port <= 65535:
        raise CameraUrlError("camera URL has an invalid port")

    try:
        literal = ipaddress.ip_address(parsed.hostname)
        addresses = {literal}
    except ValueError:
        addresses = _resolved_addresses(parsed.hostname, port)

    for address in addresses:
        unsafe_always = (
            address.is_loopback
            or address.is_link_local
            or address.is_multicast
            or address.is_unspecified
            or address.is_reserved
        )
        if unsafe_always or (address.is_private and not allow_private):
            raise CameraUrlError("camera URL resolves to a disallowed network address")
    return parsed.geturl()
