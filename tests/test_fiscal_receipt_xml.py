import pytest

from backend.services.fiscal_receipt_xml import ReceiptXmlError, parse_receipt_xml


VALID_NFE = b'''<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe">
  <NFe><infNFe Id="NFe-12345678901234567890123456789012345678901234">
    <ide><mod>55</mod><serie>7</serie><nNF>42</nNF><dhEmi>2026-10-22T10:00:00-03:00</dhEmi></ide>
    <emit><CNPJ>12345678000199</CNPJ></emit>
    <det nItem="1"><prod><cProd>INS-1</cProd><cEAN>7890000000000</cEAN><xProd>Queijo</xProd><qCom>2.0000</qCom><uCom>KG</uCom><vUnCom>12.50</vUnCom><vProd>25.00</vProd></prod></det>
    <total><ICMSTot><vNF>25.00</vNF></ICMSTot></total>
  </infNFe></NFe>
</nfeProc>'''


def test_extracts_identity_and_hashes_original_bytes():
    result = parse_receipt_xml(VALID_NFE)
    assert result.document_model == "NFe"
    assert result.access_key == "12345678901234567890123456789012345678901234"
    assert result.series == "7"
    assert result.number == "42"
    assert result.issuer_document == "12345678000199"
    assert len(result.content_sha256) == 64
    assert result.lines[0]["description"] == "Queijo"
    assert result.extracted["total_document"] == "25.00"


@pytest.mark.parametrize(
    "xml",
    [
        b'<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><NFe/>',
        b'<NFe><infNFe><ide><mod>99</mod></ide></infNFe></NFe>',
        b'<NFe><ide><mod>55</mod></ide></NFe>',
    ],
)
def test_rejects_unsafe_or_incomplete_input(xml):
    with pytest.raises(ReceiptXmlError):
        parse_receipt_xml(xml)


def test_rejects_oversized_input_before_xml_parse():
    with pytest.raises(ReceiptXmlError, match="5 MiB"):
        parse_receipt_xml(b"<NFe>" + (b"x" * (5 * 1024 * 1024)) + b"</NFe>")
