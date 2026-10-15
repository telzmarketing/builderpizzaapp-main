"""JSON-only, unprivileged queue adapter invoked by the root-owned SSL runner."""
from __future__ import annotations

import contextlib
import io
import json
import sys

from pydantic import ValidationError

from backend.core.exceptions import DomainError
from backend.database import SessionLocal
from backend.schemas.tenant_domain_ssl import WorkerFailIn, WorkerLeaseIn
from backend.services.tenant_domain_ssl_service import TenantDomainSSLService


def execute(operation, payload, db):
    service = TenantDomainSSLService(db)
    if operation in ("claim", "reconcile", "heartbeat"):
        if payload != {}:
            raise ValueError("Unexpected worker payload")
        return getattr(service, operation)()
    body = (WorkerFailIn if operation == "fail" else WorkerLeaseIn).model_validate(payload)
    if operation == "validate":
        return service.validate(str(body.job_id), body.lease_token)
    if operation == "complete":
        return service.complete(str(body.job_id), body.lease_token)
    if operation == "fail":
        return service.fail(str(body.job_id), body.lease_token, body.error_code)
    raise ValueError("Unknown worker operation")


def main():
    code = 0
    db = None
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in {"claim", "validate", "complete", "fail", "reconcile", "heartbeat"}:
            raise ValueError("Invalid operation")
        raw = sys.stdin.read(8193)
        if len(raw) > 8192:
            raise ValueError("Worker payload too large")
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("Worker payload must be an object")
        # Third-party output must never corrupt the machine-readable protocol.
        with contextlib.redirect_stdout(io.StringIO()):
            db = SessionLocal()
            result = execute(sys.argv[1], payload, db)
    except DomainError as exc:
        if db is not None:
            db.rollback()
        result = {"error_code": exc.code}
        code = 1
    except (ValueError, ValidationError):
        if db is not None:
            db.rollback()
        result = {"error_code": "INVALID_INPUT"}
        code = 2
    except Exception:
        if db is not None:
            db.rollback()
        result = {"error_code": "WORKER_ERROR"}
        code = 1
    finally:
        if db is not None:
            db.close()
    sys.stdout.write(json.dumps(result, default=lambda value: value.isoformat()) + "\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
