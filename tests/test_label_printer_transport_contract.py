import pytest
from pydantic import ValidationError

from backend.schemas.label import LabelPrinterIn


def test_network_printer_requires_host_port_and_protocol():
    with pytest.raises(ValidationError):
        LabelPrinterIn(name="Expedicao", connection_type="network")

    printer = LabelPrinterIn(
        name="Expedicao LAN",
        connection_type="network",
        network_host="192.168.1.45",
        network_port=9100,
        protocol="escpos",
    )
    assert printer.network_host == "192.168.1.45"
    assert printer.network_port == 9100
    assert printer.protocol == "escpos"


def test_browser_printer_does_not_claim_direct_ip_access():
    printer = LabelPrinterIn(name="Dialogo do sistema")
    assert printer.connection_type == "browser"
    assert printer.network_host is None
