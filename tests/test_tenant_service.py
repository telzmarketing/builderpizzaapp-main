import pytest

from backend.services.tenant_service import normalize_tenant_slug


def test_normalize_tenant_slug() -> None:
    assert normalize_tenant_slug(" Pizzaria São João ") == "pizzaria-sao-joao"


def test_normalize_tenant_slug_rejects_empty_value() -> None:
    with pytest.raises(ValueError):
        normalize_tenant_slug("---")
