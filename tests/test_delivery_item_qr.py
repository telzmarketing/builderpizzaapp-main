"""Focused contracts for signed item QR confirmation and anti-replay storage."""
from __future__ import annotations

import importlib.util
import time
from io import StringIO
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations

from backend.models.delivery import DeliveryItemConfirmation
from backend.services.qr_code_service import create_qr_payload, verify_qr_payload


ROOT = Path(__file__).parents[1]
REVISION = "20261029_delivery_item_qr_confirmations"


def _migration():
    path = ROOT / "backend/migrations/versions" / f"{REVISION}.py"
    spec = importlib.util.spec_from_file_location(REVISION, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_item_qr_is_signed_non_pii_and_verifiable():
    payload = create_qr_payload(
        tenant_id="tenant-a", order_id="order-a", kind="item",
        version_id="version-a", volume_id="volume-a", order_item_id="item-a",
    )
    claims = verify_qr_payload(payload)
    assert payload.startswith("TELZQR1.")
    assert claims["tenant_id"] == "tenant-a"
    assert claims["order_id"] == "order-a"
    assert claims["volume_id"] == "volume-a"
    assert "customer" not in payload.lower()


def test_item_qr_rejects_tampering_and_expiration():
    payload = create_qr_payload(
        tenant_id="tenant-a", order_id="order-a", kind="item",
        version_id="version-a", volume_id="volume-a", order_item_id="item-a",
        expires_at=int(time.time()) - 1,
    )
    with pytest.raises(ValueError, match="invalido ou expirado"):
        verify_qr_payload(payload)

    valid = create_qr_payload(
        tenant_id="tenant-a", order_id="order-a", kind="item",
        version_id="version-a", volume_id="volume-a", order_item_id="item-a",
    )
    parts = valid.split(".")
    parts[1] = parts[1][:-1] + ("A" if parts[1][-1] != "A" else "B")
    tampered = ".".join(parts)
    with pytest.raises(ValueError, match="invalido ou expirado"):
        verify_qr_payload(tampered)


def test_confirmation_storage_has_tenant_token_and_volume_uniqueness():
    names = {constraint.name for constraint in DeliveryItemConfirmation.__table__.constraints}
    assert "uq_delivery_item_confirmations_token" in names
    assert "uq_delivery_item_confirmations_volume" in names
    assert "delivery_id" in DeliveryItemConfirmation.__table__.columns
    assert "label_volume_id" in DeliveryItemConfirmation.__table__.columns


def test_confirmation_migration_is_additive_and_tenant_scoped():
    output = StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output}
    )
    operations = Operations(context)
    with Operations.context(operations.migration_context):
        _migration().upgrade()
    sql = output.getvalue()
    assert "CREATE TABLE delivery_item_confirmations" in sql
    assert "uq_delivery_item_confirmations_token" in sql
    assert "uq_delivery_item_confirmations_volume" in sql
    assert "tenant_id" in sql
    assert "label_volumes" in sql
