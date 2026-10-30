from backend.models.inventory import InventoryPurchase
from backend.services.fiscal_receipt_xml import ReceiptXmlError, parse_receipt_xml


def test_purchase_model_has_replenishment_audit_fields():
    assert hasattr(InventoryPurchase, "source")
    assert hasattr(InventoryPurchase, "requested_at")
    assert hasattr(InventoryPurchase, "requested_by_admin_id")


def test_fiscal_parser_rejects_incomplete_product_line():
    xml = b'''<NFe><infNFe Id="NFe-12345678901234567890123456789012345678901234">
      <ide><mod>65</mod></ide><det nItem="1"><prod><xProd>Item</xProd></prod></det>
    </infNFe></NFe>'''
    try:
        parse_receipt_xml(xml)
    except ReceiptXmlError as exc:
        assert "quantidade" in str(exc)
    else:
        raise AssertionError("linha fiscal incompleta deveria exigir revisao")


def test_fiscal_parser_rejects_invalid_line_number():
    xml = b'''<NFe><infNFe Id="NFe-12345678901234567890123456789012345678901234">
      <ide><mod>55</mod></ide><det nItem="x"><prod><xProd>Item</xProd><qCom>1</qCom><vUnCom>1</vUnCom><vProd>1</vProd></prod></det>
    </infNFe></NFe>'''
    try:
        parse_receipt_xml(xml)
    except ReceiptXmlError as exc:
        assert "Numero" in str(exc)
    else:
        raise AssertionError("numero de linha invalido deveria ser rejeitado")
