import io

import pytest
from fastapi import HTTPException

from backend.routes.customers import _parse_customer_import


def test_customer_csv_import_accepts_utf8_headers_and_rows():
    rows = _parse_customer_import(
        "clientes.csv",
        "nome,telefone,email\nAna,5511999999999,ana@example.com\n".encode("utf-8"),
    )
    assert rows == [(2, {"nome": "Ana", "telefone": "5511999999999", "email": "ana@example.com"})]


def test_customer_import_rejects_unsupported_extension():
    with pytest.raises(HTTPException) as error:
        _parse_customer_import("clientes.txt", b"nome,telefone\nAna,5511999999999\n")
    assert getattr(error.value, "status_code", None) == 422
