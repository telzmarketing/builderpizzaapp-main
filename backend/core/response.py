"""
Standardized API response envelope.

Every endpoint returns one of two shapes:

  Success:
    {
      "success": true,
      "data":    <serialized payload>,
      "message": "optional human-readable note"   ← omitted when None
    }

  Error:
    {
      "success": false,
      "error": {
        "code":    "DomainErrorClassName",
        "message": "Mensagem legível."
      }
    }

Usage in routes:
    from backend.core.response import ok, created, no_content, err

    # success
    return ok(order, "Pedido criado com sucesso")
    return created(payment)
    return no_content()

    # domain error → JSONResponse with correct HTTP status
    except DomainError as exc:
        return err(exc)
"""
from __future__ import annotations

from typing import Any

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from backend.core.exceptions import DomainError


# ── Success helpers ───────────────────────────────────────────────────────────

def ok(data: Any = None, message: str | None = None, *, status_code: int = 200) -> JSONResponse:
    """HTTP 200 with optional payload and message."""
    content: dict = {"success": True, "data": jsonable_encoder(data)}
    if message:
        content["message"] = message
    return JSONResponse(content=content, status_code=status_code)


def created(data: Any = None, message: str | None = None) -> JSONResponse:
    """HTTP 201 Created."""
    return ok(data, message, status_code=201)


def no_content() -> JSONResponse:
    """HTTP 204 No Content."""
    return JSONResponse(content=None, status_code=204)


# ── Error helper ──────────────────────────────────────────────────────────────

def err(exc: DomainError) -> JSONResponse:
    """Convert a DomainError into a standardized error response."""
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "success": False,
            "error": {
                "code":    exc.code,
                "message": exc.message,
            },
        },
    )


def err_msg(message: str, *, code: str = "Error", status_code: int = 400) -> JSONResponse:
    """Convenience for ad-hoc error messages (no DomainError instance needed)."""
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": {
                "code":    code,
                "message": message,
            },
        },
    )
