"""Security primitives shared by platform operational read models."""
from __future__ import annotations

import json
import os
import re
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.config import get_settings


MAX_SNAPSHOT_BYTES = 1_048_576
IDENTIFIER_RE = re.compile(r"[^a-z0-9_.:-]+")
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
IPV4_RE = re.compile(r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?!\d)")
PHONE_RE = re.compile(r"(?<!\w)\+?\d[\d ()-]{7,}\d(?!\w)")
LINUX_PATH_RE = re.compile(r"(?<!\w)/(?:[\w.@+-]+/)+[\w.@+-]*")
WINDOWS_PATH_RE = re.compile(r"\b[A-Za-z]:\\(?:[^\s\\]+\\)*[^\s\\]*")
BEARER_AUTH_RE = re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/=-]+")
BASIC_AUTH_RE = re.compile(
    r"(?i)\bbasic\s+(?:[a-z0-9+/]{4}){2,}"
    r"(?:[a-z0-9+/]{2}==|[a-z0-9+/]{3}=)?(?![a-z0-9+/=])"
)
URI_CREDENTIAL_RE = re.compile(r"(?i)([a-z][a-z0-9+.-]*://)[^/@\s:]+(?::[^/@\s]*)?@")
# Match the complete assignment key while requiring a sensitive identifier
# segment. Real provider fields commonly qualify the segment (for example
# ``mp_access_token`` or ``stripe_secret_key``); matching only the bare name
# would leave their values in persisted operational errors. Segment boundaries
# keep unrelated words such as ``tokenizer`` and ``secretary`` untouched.
SENSITIVE_KEY_PATTERN = r"""
    (?:[a-z0-9]+[_-])*
    (?:
        password(?:[_-]?hash)?
        |passwd
        |(?:client[_-])?secret(?:[_-]?key)?
        |(?:access[_-]|refresh[_-])?token(?:[_-]?hash)?
        |api[_-]?key
        |authorization
        |cookie
    )
    (?:[_-][a-z0-9]+)*
"""
SENSITIVE_HEADER_RE = re.compile(
    r"(?P<prefix>(?<![\w-])(?:authorization|cookie)\s*:\s*)[^\r\n]+",
    re.IGNORECASE,
)
SENSITIVE_QUOTED_ASSIGNMENT_RE = re.compile(
    rf"""
    (?P<prefix>
        (?<![\w-])
        (?P<key_quote>["']?)
        {SENSITIVE_KEY_PATTERN}
        (?P=key_quote)
        (?![\w-])
        \s*[:=]\s*
    )
    (?P<value>
        "(?:\\.|[^"\\])*"
        |
        '(?:\\.|[^'\\])*'
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)
SENSITIVE_UNQUOTED_ASSIGNMENT_RE = re.compile(
    rf"""
    (?P<prefix>
        (?<![\w-])
        (?P<key_quote>["']?)
        {SENSITIVE_KEY_PATTERN}
        (?P=key_quote)
        (?![\w-])
        \s*[:=]
    )
    (?!\s*["'])
    (?P<spacing>\s*)
    [^\r\n,;&]+
    """,
    re.IGNORECASE | re.VERBOSE,
)
LONG_SECRET_RE = re.compile(r"\b[A-Za-z0-9_+/=-]{32,}\b")


class PlatformOperationNotFound(LookupError):
    pass


class PlatformOperationConflict(RuntimeError):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def safe_identifier(value: Any, *, default: str = "unknown", max_length: int = 80) -> str:
    normalized = str(value or "").strip().lower().replace(" ", "_")
    normalized = IDENTIFIER_RE.sub("", normalized)[:max_length]
    return normalized or default


def safe_label(value: Any, *, default: str = "Nao informado", max_length: int = 200) -> str:
    normalized = " ".join(str(value or "").split())[:max_length]
    return normalized or default


def redact_text(value: Any, *, max_length: int = 500) -> str:
    """Redact common secret and PII forms before data reaches persistence/API."""
    text_value = str(value or "")
    text_value = SENSITIVE_HEADER_RE.sub(
        lambda match: f"{match.group('prefix')}[REDACTED]", text_value
    )
    text_value = BEARER_AUTH_RE.sub("Bearer [REDACTED]", text_value)
    text_value = BASIC_AUTH_RE.sub("Basic [REDACTED]", text_value)
    text_value = URI_CREDENTIAL_RE.sub(r"\1[REDACTED]@", text_value)
    text_value = SENSITIVE_QUOTED_ASSIGNMENT_RE.sub(
        lambda match: (
            f"{match.group('prefix')}"
            f"{match.group('value')[0]}[REDACTED]{match.group('value')[-1]}"
        ),
        text_value,
    )
    text_value = SENSITIVE_UNQUOTED_ASSIGNMENT_RE.sub(
        lambda match: (
            f"{match.group('prefix')}{match.group('spacing')}[REDACTED]"
        ),
        text_value,
    )
    text_value = " ".join(text_value.split())
    text_value = EMAIL_RE.sub("[EMAIL]", text_value)
    text_value = IPV4_RE.sub("[IP]", text_value)
    text_value = PHONE_RE.sub("[PHONE]", text_value)
    text_value = WINDOWS_PATH_RE.sub("[PATH]", text_value)
    text_value = LINUX_PATH_RE.sub("[PATH]", text_value)
    text_value = LONG_SECRET_RE.sub("[REDACTED]", text_value)
    return text_value[:max_length] or "Erro operacional sem mensagem publica."


def non_negative_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError, OverflowError):
        return 0


def bounded_percent(value: Any) -> float:
    try:
        return round(min(100.0, max(0.0, float(value or 0))), 2)
    except (TypeError, ValueError, OverflowError):
        return 0.0


def normalize_health(value: Any) -> str:
    status = safe_identifier(value)
    if status in {"ok", "up", "online", "active", "running", "healthy", "success", "validated"}:
        return "healthy"
    if status in {"warning", "attention", "degraded", "stale", "partial"}:
        return "degraded"
    if status in {"down", "offline", "error", "failed", "critical", "unhealthy", "stopped"}:
        return "critical"
    return "unknown"


class PlatformSnapshotReader:
    """Read bounded, regular JSON files below the configured collector root."""

    def __init__(self, root: str | Path | None = None):
        self._enforce_root_ownership = root is None
        configured = root if root is not None else get_settings().PLATFORM_MONITORING_SNAPSHOT_DIR
        self.root = Path(configured).resolve(strict=False)

    def _trusted_root(self) -> bool:
        if not self._enforce_root_ownership:
            return True
        try:
            root_stat = self.root.stat()
        except OSError:
            return False
        return (
            stat.S_ISDIR(root_stat.st_mode)
            and root_stat.st_uid == 0
            and stat.S_IMODE(root_stat.st_mode) & 0o022 == 0
        )

    def _path(self, relative_path: str) -> Path:
        candidate = (self.root / relative_path).resolve(strict=False)
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("snapshot fora do diretorio permitido") from exc
        return candidate

    def read_json(self, relative_path: str) -> dict[str, Any] | None:
        if not self._trusted_root():
            return None
        path = self._path(relative_path)
        try:
            if path.is_symlink():
                return None
            file_stat = path.stat()
            if not stat.S_ISREG(file_stat.st_mode) or file_stat.st_size > MAX_SNAPSHOT_BYTES:
                return None
            flags = os.O_RDONLY
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            descriptor = os.open(path, flags)
            try:
                with os.fdopen(descriptor, "r", encoding="utf-8") as handle:
                    payload = json.load(handle)
            except Exception:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
                return None
        except (OSError, ValueError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    def read_directory(self, relative_dir: str, *, limit: int = 100) -> list[dict[str, Any]]:
        if not self._trusted_root():
            return []
        directory = self._path(relative_dir)
        try:
            if directory.is_symlink() or not directory.is_dir():
                return []
            paths = sorted(directory.glob("*.json"), key=lambda item: item.name, reverse=True)[:limit]
        except OSError:
            return []
        payloads: list[dict[str, Any]] = []
        for path in paths:
            payload = self.read_json(f"{relative_dir}/{path.name}")
            if payload is not None:
                payloads.append(payload)
        return payloads


def snapshot_freshness(payload: dict[str, Any] | None, *, max_age_seconds: int) -> tuple[datetime, bool]:
    generated_at = parse_datetime((payload or {}).get("generated_at"))
    if generated_at is None:
        return utcnow(), True
    age = max(0.0, (utcnow() - generated_at).total_seconds())
    return generated_at, age > max_age_seconds
