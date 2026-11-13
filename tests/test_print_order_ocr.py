from backend.services.print_order_ocr import extract_local_text


def test_local_ocr_is_fail_closed_when_optional_stack_is_unavailable(monkeypatch):
    monkeypatch.setitem(__import__("sys").modules, "pytesseract", None)
    assert extract_local_text(b"not-an-image", "image/jpeg") is None


def test_local_ocr_skips_pdf_without_remote_or_text_fallback():
    assert extract_local_text(b"%PDF-1.7", "application/pdf") is None
