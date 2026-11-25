from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from backend.schemas.finance import FinanceContractIn, FinanceContractOut
from backend.services.finance_service import FinanceInvalidReference, FinanceService


def _service() -> FinanceService:
    return object.__new__(FinanceService)


def test_contract_payload_preserves_dates_amount_and_status():
    payload = FinanceContractIn.model_validate({
        "counterparty_id": "fin-cpt-supplier",
        "title": "Contrato de insumos",
        "start_date": "2026-01-01",
        "end_date": "2026-12-31",
        "renewal_date": "2026-11-30",
        "amount": "1250.90",
        "billing_period": "monthly",
        "status": "active",
    })

    assert payload.start_date == date(2026, 1, 1)
    assert payload.amount == Decimal("1250.90")
    assert payload.status == "active"


def test_contract_serializer_exposes_supplier_and_contract_terms():
    row = SimpleNamespace(
        id="fin-contract-1",
        tenant_id="tenant-1",
        counterparty_id="fin-cpt-1",
        counterparty=SimpleNamespace(name="Fornecedor A"),
        title="Contrato anual",
        contract_number="CNT-001",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        renewal_date=date(2026, 11, 30),
        amount=Decimal("500.00"),
        billing_period="monthly",
        status="active",
        notes=None,
        created_by_admin_id=None,
        created_at=None,
        updated_at=None,
    )

    result = _service()._serialize_contract(row)
    response = FinanceContractOut.model_validate(result)

    assert response.counterparty_name == "Fornecedor A"
    assert response.amount == Decimal("500.00")
    assert response.status == "active"


def test_contract_payload_rejects_negative_amount():
    with pytest.raises(ValueError):
        FinanceContractIn.model_validate({
            "counterparty_id": "fin-cpt-supplier",
            "title": "Contrato inválido",
            "start_date": "2026-01-01",
            "amount": "-1.00",
        })
