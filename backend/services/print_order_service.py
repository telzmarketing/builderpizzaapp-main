"""Safe, deterministic Print Pedido capture/review/confirmation flow."""
from __future__ import annotations

import re
import unicodedata
import uuid
from pathlib import Path
from typing import Iterable

from fastapi import UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.core.tenant_context import TenantContext, TenantSource
from backend.core.tenant_execution import tenant_upload_path
from backend.database import SessionLocal
from backend.models.order import Order
from backend.models.inventory import InventoryRecipeVersion
from backend.models.product import Product, ProductCrustType, ProductDrinkVariant, ProductSize
from backend.models.print_order import PrintOrderCatalogMapping, PrintOrderImport, PrintOrderItem
from backend.models.upload_asset import TenantUploadAsset
from backend.schemas.order import CartItemIn, CheckoutIn, DeliveryAddressIn, FlavorIn
from backend.schemas.print_order import PrintOrderItemReviewIn, PrintOrderMappingIn, PrintOrderReviewIn
from backend.services.idempotency_service import IdempotencyService
from backend.services.order_service import OrderService
from backend.services.tenant_upload_service import TenantUploadService
from backend.services.print_order_ocr import extract_local_text
from backend.services.print_order_ai import extract_print_order_with_vision

MAX_BYTES = 10 * 1024 * 1024
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif", "application/pdf"}
EXTENSIONS = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/gif": "gif", "application/pdf": "pdf"}
ITEM_RE = re.compile(r"^\s*(?:(\d+)\s*[xX]\s*)?(?:item\s*[:\-]\s*)?(.+?)\s*$")
NUMBER_RE = re.compile(r"(?:pedido|order)\s*(?:n[ºo°.]?|#|number)?\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-/]{2,})", re.I)
TOTAL_RE = re.compile(r"(?:total|valor\s+total)\s*[:\-]?\s*(?:R\$\s*)?([0-9]+(?:[.,][0-9]{2})?)", re.I)
MONEY_RE = re.compile(r"-?\s*(?:R\$\s*)?(?:\d{1,3}(?:\.\d{3})*|\d+)(?:[,.]\d{2})")


def normalize_print_text(value: str | None) -> str:
    raw = unicodedata.normalize("NFD", str(value or ""))
    raw = raw.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", raw)).strip()


def print_order_external_reference(tenant_id: str, platform: str, external_order_number: str) -> str:
    """Stable reference shared by concurrent confirmations of one partner order."""
    return f"print-pedido:{tenant_id}:{normalize_print_text(platform)}:{normalize_print_text(external_order_number)}"


def build_print_order_cart_item(item, catalog_products: list[Product], *, selected_size_id: str | None = None,
                                selected_crust_type_id: str | None = None, selected_border_id: str | None = None,
                                selected_drink_variant_id: str | None = None, add_ons: list[str] | None = None,
                                option_selections: list[dict] | None = None) -> CartItemIn:
    """Convert a reviewed line without treating unresolved labels as catalog data."""
    supported = {"notes", "selected_size_id", "selected_crust_type_id", "selected_border_id", "selected_drink_variant_id", "add_on_ids", "addon_ids", "option_selections"}
    unknown = set(getattr(item, "customizations", None) or {}) - supported
    if unknown:
        raise DomainError("A composicao possui campos sem contrato de catalogo.", code="PrintOrderCompositionReviewRequired")
    primary = next((product for product in catalog_products if product.id == item.product_id), None)
    if primary is None:
        raise DomainError("Produto principal nao encontrado no catalogo do tenant.", code="PrintOrderInvalidProduct")

    raw_flavors = list(item.flavor_names or [])
    if not raw_flavors:
        flavors = [primary]
    else:
        normalized_names = [normalize_print_text(name) for name in raw_flavors]
        if any(not name for name in normalized_names):
            raise DomainError("Sabor vazio nao pode ser confirmado.", code="PrintOrderFlavorNotResolved")
        flavors = []
        for normalized_name in normalized_names:
            matches = [product for product in catalog_products
                       if product.active and normalize_print_text(product.name) == normalized_name]
            if len(matches) != 1:
                raise DomainError(
                    f"Sabor '{normalized_name}' nao foi resolvido de forma unica no catalogo.",
                    code="PrintOrderFlavorNotResolved",
                )
            flavors.append(matches[0])
        if primary.id not in {product.id for product in flavors}:
            raise DomainError("O produto principal deve integrar a composicao de sabores.", code="PrintOrderPrimaryFlavorMissing")
        if len(flavors) > 3:
            raise DomainError("A pizza possui mais de tres sabores.", code="PrintOrderFlavorDivisionInvalid")

    notes = (item.customizations or {}).get("notes")
    return CartItemIn(
        product_id=primary.id,
        quantity=item.quantity,
        selected_size=item.selected_size or "Unico",
        selected_size_id=selected_size_id,
        flavor_division=len(flavors),
        flavors=[FlavorIn(product_id=product.id, name=product.name, price=float(product.price), icon=product.icon or "") for product in flavors],
        final_price=float(item.unit_price if item.unit_price is not None else primary.price),
        add_ons=list(add_ons or []),
        option_selections=list(option_selections or []),
        selected_crust_type_id=selected_crust_type_id,
        selected_border_id=selected_border_id,
        selected_drink_variant_id=selected_drink_variant_id,
        notes=notes,
    )


def detect_platform(text: str, manual: str | None = None) -> str:
    if manual in {"ifood", "99food", "keeta", "unknown"}:
        return manual
    normalized = normalize_print_text(text)
    if "99food" in normalized or "99 food" in normalized:
        return "99food"
    if "ifood" in normalized:
        return "ifood"
    if "keeta" in normalized:
        return "keeta"
    return "unknown"


def parse_print_text(text: str | None, manual_platform: str | None = None) -> dict:
    """Parse only explicit text patterns; it never claims OCR/AI was used."""
    raw = (text or "").strip()
    platform = detect_platform(raw, manual_platform)
    number_match = NUMBER_RE.search(raw)
    total_match = TOTAL_RE.search(raw)
    items = []
    ignored = {"ifood", "99food", "keeta", "total", "subtotal", "cliente", "endereco", "pagamento"}
    for line in raw.splitlines():
        normalized_line = normalize_print_text(line)
        if NUMBER_RE.search(line) or TOTAL_RE.search(line) or normalized_line in {"ifood", "99food", "keeta", "total", "subtotal", "cliente", "endereco", "pagamento"}:
            continue
        match = ITEM_RE.match(line)
        if not match:
            continue
        name = re.sub(r"\s+(?:R\$\s*)?\d+[.,]\d{2}\s*$", "", match.group(2)).strip(" -:")
        if normalize_print_text(name) in ignored or len(name) < 2 or not re.search(r"[A-Za-zÀ-ÿ]", name):
            continue
        flavor_names: list[str] = []
        if re.search(r"(?:meia|1\s*/\s*2)", name, re.I):
            parts = re.split(r"\s*(?:/|\+|\be\b)\s*", re.sub(r"(?:meia|1\s*/\s*2)\s*", "", name, flags=re.I), maxsplit=2)
            flavor_names = [part.strip(" -:") for part in parts if len(part.strip(" -:")) >= 2]
        items.append({"external_name": name[:300], "normalized_name": normalize_print_text(name)[:300], "quantity": int(match.group(1) or 1), "flavor_names": flavor_names})
    notes = []
    if not raw:
        notes.append("Nenhum texto fornecido; OCR/IA nao configurado. Revisao manual obrigatoria.")
    if not items:
        notes.append("Nenhum item explicito foi identificado; informe os itens antes de confirmar.")
    return {"platform": platform, "external_order_number": number_match.group(1) if number_match else None,
            "printed_total": float(total_match.group(1).replace('.', '').replace(',', '.')) if total_match else None,
            "items": items, "review_notes": notes, "parser": "deterministic-v1"}


def _extract_external_order_number(lines: list[str]) -> str | None:
    """Extract only an explicit order marker; never promote arbitrary OCR text."""
    marker = re.compile(r"^\s*#\s*([A-Z0-9][A-Z0-9\-/]{2,})\b", re.I)
    labeled = re.compile(r"\b(?:pedido|order)\b\s*(?:n[ºo°.]?|#|number)?\s*[:\-#]?\s*([A-Z0-9][A-Z0-9\-/]{2,})", re.I)
    for line in lines:
        match = marker.search(line) or labeled.search(line)
        if match:
            return match.group(1)
    return None


def _is_time_line(normalized_line: str) -> bool:
    # normalize_print_text removes ':' and '.', so accept the normalized
    # space-separated form as well as raw OCR text.
    return bool(re.search(r"\b\d{1,2}\s*(?::|\.)\s*\d{2}\b", normalized_line)
                or re.search(r"\b\d{1,2}\s+\d{2}\b", normalized_line))


def _extract_customer_name(lines: list[str]) -> str | None:
    """Read a customer only from an explicit customer section of the receipt."""
    normalized = [normalize_print_text(line) for line in lines]
    for index, normalized_line in enumerate(normalized):
        if normalized_line.startswith("cliente ") or normalized_line.startswith("cliente:"):
            value = re.sub(r"^cliente\s*[:\-]?\s*", "", lines[index], flags=re.I).strip(" |:-")
            return value or None

    marker_index = next((index for index, value in enumerate(normalized)
                         if value in {"novos clientes", "novos"} or value.startswith("novos clientes ")), None)
    if marker_index is None:
        # Keeta may omit/blur the "Novos clientes" label. In that case only
        # accept the first human-looking line after the pickup/delivery time
        # and before payment/item markers; never promote arbitrary OCR text.
        time_index = next((index for index, value in enumerate(normalized) if _is_time_line(value)), -1)
        for index in range(time_index + 1, len(lines)):
            value = lines[index].strip(" |:-")
            normalized_value = normalized[index]
            if normalized_value in {"pago", "1 item", "obs do pedido"} or normalized_value.startswith("obs do pedido"):
                break
            if value and not _is_time_line(normalized_value) and re.search(r"[A-Za-zÀ-ÿ]", value) and len(value) >= 4:
                return value
        return None
    time_index = next((index for index in range(marker_index - 1, -1, -1) if _is_time_line(normalized[index])), -1)
    candidates: list[str] = []
    for index in range(time_index + 1, marker_index):
        value = lines[index].strip(" |:-")
        normalized_value = normalized[index]
        if not value or _is_time_line(normalized_value) or normalized_value in {"retirada as", "retirada", "entrega"}:
            continue
        if re.fullmatch(r"[\d.,:/ -]+", value) or not re.search(r"[A-Za-zÀ-ÿ�]", value):
            continue
        candidates.append(value)
    return " ".join(candidates).strip() or None


def _extract_payment_method(lines: list[str]) -> str | None:
    """Return a payment label only when the receipt explicitly states it."""
    for line in lines:
        normalized = normalize_print_text(line.strip(" |:-"))
        if normalized == "pago" or normalized.startswith("pagamento pago"):
            return "Pago"
    return None


def _parse_money(value: str | None) -> float | None:
    if not value:
        return None
    value = value.replace("R$", "").replace(" ", "").strip()
    try:
        if "," in value:
            value = value.replace(".", "").replace(",", ".")
        return round(float(value), 2)
    except ValueError:
        return None


def _money_after_label(line: str, labels: tuple[str, ...]) -> float | None:
    normalized = normalize_print_text(line)
    if not any(label in normalized for label in labels):
        return None
    matches = MONEY_RE.findall(line)
    return _parse_money(matches[-1]) if matches else None


def _extract_financials(lines: list[str]) -> dict:
    financials = {
        "subtotal": None,
        "delivery_fee": None,
        "service_fee": None,
        "store_discount": None,
        "platform_discount": None,
        "total_paid": None,
    }
    for line in lines:
        normalized = normalize_print_text(line)
        if normalized.startswith("total do item") or normalized.startswith("subtotal"):
            financials["subtotal"] = _money_after_label(line, ("total do item", "subtotal"))
        elif normalized.startswith("taxa de entrega"):
            financials["delivery_fee"] = _money_after_label(line, ("taxa de entrega",))
        elif normalized.startswith("taxa de servico"):
            financials["service_fee"] = _money_after_label(line, ("taxa de servico",))
        elif "promocao financiada pela loja" in normalized:
            value = _money_after_label(line, ("promocao financiada pela loja",))
            financials["store_discount"] = abs(value) if value is not None else None
        elif "promocao financiada pela keeta" in normalized or "promocao financiada pelo keeta" in normalized:
            value = _money_after_label(line, ("promocao financiada pela keeta", "promocao financiada pelo keeta"))
            financials["platform_discount"] = abs(value) if value is not None else None
        elif normalized.startswith("valor pago pelo cliente"):
            financials["total_paid"] = _money_after_label(line, ("valor pago pelo cliente",))
    if financials["total_paid"] is None:
        for index, line in enumerate(lines):
            if normalize_print_text(line).startswith("valor pago pelo cliente") and index + 1 < len(lines):
                financials["total_paid"] = _parse_money((MONEY_RE.findall(lines[index + 1]) or [""])[-1])
    return financials


def _reconcile_financials(financials: dict) -> dict:
    fields = [financials.get(key) for key in ("subtotal", "delivery_fee", "service_fee", "store_discount", "platform_discount", "total_paid")]
    if any(value is None for value in fields):
        return {"status": "incomplete", "expected_total": None, "printed_total": financials.get("total_paid"), "delta": None}
    expected = round(float(financials["subtotal"] or 0) + float(financials["delivery_fee"] or 0) + float(financials["service_fee"] or 0) - float(financials["store_discount"] or 0) - float(financials["platform_discount"] or 0), 2)
    printed = round(float(financials["total_paid"] or 0), 2)
    delta = round(printed - expected, 2)
    return {"status": "matched" if abs(delta) <= 0.01 else "divergent", "expected_total": expected, "printed_total": printed, "delta": delta}


def _extract_fulfillment_type(lines: list[str]) -> str:
    normalized = " ".join(normalize_print_text(line) for line in lines)
    if "retirada as" in normalized or "retirada" in normalized:
        return "pickup"
    if "entrega" in normalized:
        return "delivery"
    return "unknown"


def _clean_item_line(line: str) -> str:
    value = re.sub(r"[^\S\r\n]+", " ", line.replace("�", "")).strip(" |:-")
    return re.sub(r"\s+(?:R\$\s*)?\d+[.,]\d{2}\s*$", "", value).strip(" |:-")


def _parse_item_block(lines: list[str]) -> list[dict]:
    """Parse only the item section and join OCR-wrapped product lines."""
    start = next((index for index, line in enumerate(lines)
                  if "itens" in normalize_print_text(line) and ("qtd" in normalize_print_text(line) or "preco" in normalize_print_text(line))), None)
    if start is None:
        start = next((index for index, line in enumerate(lines) if normalize_print_text(line) in {"itens", "qtd itens"}), None)
    if start is None:
        return []
    end = next((index for index in range(start + 1, len(lines))
                if normalize_print_text(lines[index]).startswith("total do item")), None)
    if end is None:
        return []

    grouped: list[dict] = []
    current: dict | None = None
    for raw_line in lines[start + 1:end]:
        line = _clean_item_line(raw_line)
        normalized = normalize_print_text(line)
        if (not line or normalized in {"preco", "preco rs", "r", "rs", "qtd", "itens", "qtd itens"}
                or "preco rs" in normalized or normalized.startswith("obs do pedido")
                or re.fullmatch(r"[\d.,$ -]+", line)):
            continue
        quantity_match = re.match(r"^\D*?(\d+)\s*[xX]\s+(.+)$", line)
        half_flavor = bool(re.match(r"^(?:meia|1\s*/\s*2)\b", line, re.I))
        if current is None or quantity_match or half_flavor:
            if current is not None:
                grouped.append(current)
            current = {"name": quantity_match.group(2) if quantity_match else line,
                       "quantity": int(quantity_match.group(1)) if quantity_match else 1}
        else:
            current["name"] = f"{current['name']} {line}".strip()
    if current is not None:
        grouped.append(current)

    items = []
    for entry in grouped:
        name = entry["name"][:300]
        if len(name) < 2 or not re.search(r"[A-Za-zÀ-ÿ]", name):
            continue
        flavor_names: list[str] = []
        if re.search(r"(?:meia|1\s*/\s*2)", name, re.I):
            parts = re.split(r"\s*(?:/|\+|\be\b)\s*", re.sub(r"(?:meia|1\s*/\s*2)\s*", "", name, flags=re.I), maxsplit=2)
            flavor_names = [part.strip(" -:") for part in parts if len(part.strip(" -:")) >= 2]
        items.append({"external_name": name, "normalized_name": normalize_print_text(name)[:300], "quantity": entry["quantity"], "flavor_names": flavor_names})
    return items


def parse_print_text(text: str | None, manual_platform: str | None = None) -> dict:
    """Parse explicit receipt sections and keep uncertain fields for human review."""
    raw = (text or "").strip()
    lines = raw.splitlines()
    platform = detect_platform(raw, manual_platform)
    number = _extract_external_order_number(lines)
    financials = _extract_financials(lines)
    total_match = TOTAL_RE.search(raw)
    items = _parse_item_block(lines)
    if not items:
        # Preserve the original deterministic line parser for non-Keeta formats.
        ignored = {"ifood", "99food", "keeta", "total", "subtotal", "cliente", "endereco", "pagamento"}
        for line in lines:
            normalized_line = normalize_print_text(line)
            if NUMBER_RE.search(line) or TOTAL_RE.search(line) or normalized_line in ignored:
                continue
            match = ITEM_RE.match(line)
            if not match:
                continue
            name = re.sub(r"\s+(?:R\$\s*)?\d+[.,]\d{2}\s*$", "", match.group(2)).strip(" -:")
            if normalize_print_text(name) in ignored or len(name) < 2 or not re.search(r"[A-Za-zÀ-ÿ]", name):
                continue
            flavor_names: list[str] = []
            if re.search(r"(?:meia|1\s*/\s*2)", name, re.I):
                parts = re.split(r"\s*(?:/|\+|\be\b)\s*", re.sub(r"(?:meia|1\s*/\s*2)\s*", "", name, flags=re.I), maxsplit=2)
                flavor_names = [part.strip(" -:") for part in parts if len(part.strip(" -:")) >= 2]
            items.append({"external_name": name[:300], "normalized_name": normalize_print_text(name)[:300], "quantity": int(match.group(1) or 1), "flavor_names": flavor_names})
    fulfillment_type = _extract_fulfillment_type(lines)
    reconciliation = _reconcile_financials(financials)
    notes = []
    if not raw:
        notes.append("Nenhum texto fornecido; OCR/IA nao configurado. Revisao manual obrigatoria.")
    if not items:
        notes.append("Nenhum item explicito foi identificado; informe os itens antes de confirmar.")
    if not number:
        notes.append("Numero original nao identificado; revise a comanda.")
    if fulfillment_type == "unknown":
        notes.append("Tipo de atendimento nao identificado; revise entrega ou retirada.")
    if reconciliation["status"] == "incomplete":
        notes.append("Conciliação financeira incompleta; revise subtotal, taxas, descontos e valor pago.")
    elif reconciliation["status"] == "divergent":
        notes.append(f"Divergência financeira de R$ {reconciliation['delta']:.2f}; confirmação bloqueada até a revisão.")
    return {"platform": platform, "external_order_number": number,
            "customer_name": _extract_customer_name(lines), "payment_method": _extract_payment_method(lines),
            "fulfillment_type": fulfillment_type, "printed_total": financials.get("total_paid") or (float(total_match.group(1).replace('.', '').replace(',', '.')) if total_match else None),
            "financials": financials, "reconciliation": reconciliation,
            "items": items, "review_notes": notes, "parser": "deterministic-v1"}


def _magic_ok(content_type: str, data: bytes) -> bool:
    return ((content_type == "application/pdf" and data.startswith(b"%PDF-")) or
            (content_type == "image/jpeg" and data.startswith(b"\xff\xd8\xff")) or
            (content_type == "image/png" and data.startswith(b"\x89PNG\r\n\x1a\n")) or
            (content_type == "image/gif" and data[:6] in {b"GIF87a", b"GIF89a"}) or
            (content_type == "image/webp" and data[:4] == b"RIFF" and data[8:12] == b"WEBP"))


class PrintOrderService:
    def __init__(self, db: Session, tenant_id: str, admin_id: str, tenant_context: TenantContext | None = None):
        self.db, self.tenant_id, self.admin_id = db, tenant_id, admin_id
        self.tenant_context = tenant_context

    def _get(self, import_id: str, *, for_update: bool = False) -> PrintOrderImport:
        query = self.db.query(PrintOrderImport).filter(PrintOrderImport.id == import_id, PrintOrderImport.tenant_id == self.tenant_id)
        if for_update:
            query = query.with_for_update()
        row = query.first()
        if not row:
            raise DomainError("Importacao Print Pedido nao encontrada.", code="PrintOrderImportNotFound")
        return row

    def _items(self, import_id: str) -> list[PrintOrderItem]:
        return self.db.query(PrintOrderItem).filter(PrintOrderItem.import_id == import_id, PrintOrderItem.tenant_id == self.tenant_id).order_by(PrintOrderItem.position).all()

    def _apply_mapping(self, row: PrintOrderItem, platform: str) -> None:
        mapping = self.db.query(PrintOrderCatalogMapping).filter_by(tenant_id=self.tenant_id, platform=platform, normalized_external_name=row.normalized_name, status="approved").first()
        if mapping:
            row.product_id, row.match_status, row.match_reason = mapping.product_id, "matched", "approved_mapping"

    async def capture(self, file: UploadFile, platform: str | None, extracted_text: str | None) -> PrintOrderImport:
        content_type = (file.content_type or "").lower().strip()
        if content_type not in ALLOWED_TYPES:
            raise DomainError("Tipo de arquivo nao permitido. Use JPEG, PNG, WebP, GIF ou PDF.", code="PrintOrderInvalidFileType")
        data = await file.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise DomainError("Arquivo excede o limite de 10 MB.", code="PrintOrderFileTooLarge")
        if not _magic_ok(content_type, data):
            raise DomainError("O conteudo do arquivo nao corresponde ao tipo declarado.", code="PrintOrderInvalidFileSignature")
        filename = f"{uuid.uuid4().hex}.{EXTENSIONS[content_type]}"
        context = self.tenant_context or TenantContext(tenant_id=self.tenant_id, source=TenantSource.JOB)
        path = tenant_upload_path(Path("uploads"), context, filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        try:
            from backend.models.admin import AdminUser
            asset = TenantUploadService(self.db).create_asset(context=context, admin=self.db.query(AdminUser).filter_by(id=self.admin_id).one(), filename=filename, original_filename=file.filename or filename, content_type=content_type, byte_size=len(data), visibility="private")
            vision_parsed, vision_reason = extract_print_order_with_vision(self.db, self.tenant_id, data, content_type, platform)
            ocr_result = None if extracted_text and extracted_text.strip() or vision_parsed else extract_local_text(data, content_type)
            parsed_text = extracted_text if extracted_text and extracted_text.strip() else (ocr_result.text if ocr_result else None)
            parsed = vision_parsed or parse_print_text(parsed_text, platform)
            parsed["platform"] = parsed.get("platform") if parsed.get("platform") in {"ifood", "99food", "keeta", "unknown"} else (platform or "unknown")
            if vision_parsed:
                parsed["review_notes"] = list(parsed.get("review_notes", []))
                if vision_reason:
                    parsed["review_notes"].append("Visao multimodal indisponivel; usado fallback local/manual.")
            if ocr_result is not None and not vision_parsed:
                parsed["review_notes"] = list(parsed.get("review_notes", []))
                parsed["review_notes"].insert(0, "Texto obtido por OCR local; revise todos os campos antes de confirmar.")
                parsed["parser"] = "deterministic-v1+ocr-local"
            elif not vision_parsed and not (extracted_text and extracted_text.strip()) and content_type.startswith("image/"):
                parsed["review_notes"] = list(parsed.get("review_notes", []))
                parsed["review_notes"].insert(0, "OCR local indisponivel; instale/configure Tesseract local ou cole o texto OCR para revisao manual.")
            row = PrintOrderImport(id=str(uuid.uuid4()), tenant_id=self.tenant_id, source_asset_id=asset.id, source_filename=file.filename or filename, source_content_type=content_type, platform=parsed["platform"], external_order_number=parsed.get("external_order_number"), dedupe_key=(f"{self.tenant_id}:{parsed['platform']}:{parsed['external_order_number']}" if parsed["platform"] != "unknown" and parsed.get("external_order_number") else None), status="awaiting_review", parser_version=parsed.get("parser", "deterministic-v1"), raw_text=parsed_text, normalized_payload=parsed, review_notes=parsed.get("review_notes", []), created_by_admin_id=self.admin_id)
            self.db.add(row); self.db.flush()
            for position, item in enumerate(parsed.get("items", [])):
                child = PrintOrderItem(id=str(uuid.uuid4()), tenant_id=self.tenant_id, import_id=row.id, position=position, external_name=item["external_name"], normalized_name=item.get("normalized_name") or normalize_print_text(item["external_name"]), quantity=item["quantity"], flavor_names=item.get("flavor_names", []), unit_price=item.get("unit_price"), total_price=item.get("total_price"))
                self.db.add(child); self.db.flush(); self._apply_mapping(child, row.platform)
            if row.external_order_number:
                existing = self.db.query(PrintOrderImport).filter(PrintOrderImport.tenant_id == self.tenant_id, PrintOrderImport.dedupe_key == row.dedupe_key, PrintOrderImport.id != row.id).first()
                if existing:
                    row.dedupe_key = None; row.status = "duplicate"; row.duplicate_of_id = existing.id; row.review_notes = ["Este pedido ja foi importado."]
            self.db.commit(); self.db.refresh(row); return row
        except IntegrityError:
            self.db.rollback(); path.unlink(missing_ok=True)
            raise DomainError("Este pedido ja foi importado ou esta sendo processado.", code="PrintOrderDuplicate",)
        except Exception:
            self.db.rollback(); path.unlink(missing_ok=True); raise

    def review(self, import_id: str, body: PrintOrderReviewIn) -> PrintOrderImport:
        row = self._get(import_id)
        if row.status in {"imported", "duplicate", "cancelled"}:
            raise DomainError("Importacao encerrada nao pode ser revisada.", code="PrintOrderClosed")
        if body.platform: row.platform = body.platform
        for key in ("store_identifier", "external_order_number"):
            value = getattr(body, key)
            if value is not None: setattr(row, key, value.strip() or None)
        payload = dict(row.normalized_payload or {})
        for key in ("customer_name", "customer_phone", "delivery_street", "delivery_city", "delivery_complement", "payment_method"):
            value = getattr(body, key)
            if value is not None:
                payload[key] = value.strip() or None
        payload.update({"platform": row.platform, "external_order_number": row.external_order_number, "fulfillment_type": body.fulfillment_type})
        financials = dict(payload.get("financials") or {})
        for key in ("subtotal", "delivery_fee", "service_fee", "store_discount", "platform_discount", "total_paid"):
            value = getattr(body, key)
            if value is not None:
                financials[key] = float(value)
        if body.printed_total is not None and body.total_paid is None:
            financials["total_paid"] = float(body.printed_total)
        payload["financials"] = financials
        payload["printed_total"] = financials.get("total_paid")
        payload["reconciliation"] = _reconcile_financials(financials)
        self.db.query(PrintOrderItem).filter(PrintOrderItem.import_id == row.id, PrintOrderItem.tenant_id == self.tenant_id).delete(synchronize_session=False)
        for position, item in enumerate(body.items):
            normalized = normalize_print_text(item.external_name)
            child = PrintOrderItem(id=str(uuid.uuid4()), tenant_id=self.tenant_id, import_id=row.id, position=position, external_name=item.external_name.strip(), normalized_name=normalized, product_id=item.product_id, quantity=item.quantity, selected_size=item.selected_size, flavor_names=item.flavor_names, customizations=item.customizations, unit_price=item.unit_price, total_price=item.total_price, match_status="matched" if item.product_id else "unmatched", match_reason="operator_review" if item.product_id else None)
            self.db.add(child)
            if not item.product_id: self._apply_mapping(child, row.platform)
        reviewed_items = self._items(row.id)
        row.normalized_payload = payload
        row.status = "ready" if self._is_ready(row, reviewed_items, payload) else "awaiting_review"
        row.review_notes = [] if row.status == "ready" else self._review_blockers(row, reviewed_items, payload)
        self.db.commit(); self.db.refresh(row); return row

    @staticmethod
    def _is_ready(row: PrintOrderImport, items: list[PrintOrderItem], payload: dict) -> bool:
        if row.platform == "unknown" or not row.external_order_number or not payload.get("customer_name") or not payload.get("payment_method"):
            return False
        if payload.get("fulfillment_type") == "delivery" and not (payload.get("customer_phone") and payload.get("delivery_city")):
            return False
        if not items or any(not item.product_id for item in items):
            return False
        return (payload.get("reconciliation") or {}).get("status") == "matched"

    @staticmethod
    def _review_blockers(row: PrintOrderImport, items: list[PrintOrderItem], payload: dict) -> list[str]:
        blockers = []
        if row.platform == "unknown": blockers.append("Plataforma nao identificada.")
        if not row.external_order_number: blockers.append("Numero original nao identificado.")
        if not payload.get("customer_name"): blockers.append("Cliente nao identificado.")
        if not payload.get("payment_method"): blockers.append("Pagamento nao identificado.")
        if payload.get("fulfillment_type") == "delivery" and not payload.get("customer_phone"): blockers.append("Telefone obrigatorio para entrega.")
        if payload.get("fulfillment_type") == "delivery" and not payload.get("delivery_city"): blockers.append("Cidade obrigatoria para entrega.")
        if not items: blockers.append("Nenhum item identificado.")
        if any(not item.product_id for item in items): blockers.append("Todos os itens devem ser mapeados ao catalogo.")
        reconciliation_status = (payload.get("reconciliation") or {}).get("status")
        if reconciliation_status != "matched": blockers.append("Conciliação financeira incompleta ou divergente.")
        return blockers

    def confirm(self, import_id: str, key: str) -> PrintOrderImport:
        row = self._get(import_id, for_update=True)
        if row.order_id: return row
        if row.status == "duplicate": return row
        items = self._items(row.id)
        payload = row.normalized_payload or {}
        required = [row.external_order_number, payload.get("customer_name"), payload.get("payment_method")]
        payment_label = normalize_print_text(payload.get("payment_method"))
        pickup = payload.get("fulfillment_type") == "pickup"
        if not pickup:
            required.extend([payload.get("customer_phone"), payload.get("delivery_city")])
        if (row.platform == "unknown" or not all(required) or not items or any(not i.product_id for i in items)
                or payment_label in {"pago", "paid"}
                or (payload.get("reconciliation") or {}).get("status") != "matched"):
            raise DomainError("Revise plataforma, numero, cliente, entrega, pagamento e mapeamento dos itens antes de confirmar.", code="PrintOrderReviewRequired")
        supported_composition_keys = {"notes", "selected_size_id", "selected_crust_type_id", "selected_border_id", "selected_drink_variant_id", "add_on_ids", "addon_ids", "option_selections"}
        unsupported_compositions = [item for item in items if set(item.customizations or {}) - supported_composition_keys]
        if unsupported_compositions:
            raise DomainError(
                "A composição de sabores, bordas ou adicionais exige revisão no configurador do pedido antes da confirmação.",
                code="PrintOrderCompositionReviewRequired",
            )
        duplicate = self.db.query(PrintOrderImport).filter(PrintOrderImport.tenant_id == self.tenant_id, PrintOrderImport.platform == row.platform, PrintOrderImport.external_order_number == row.external_order_number, PrintOrderImport.id != row.id, PrintOrderImport.order_id.isnot(None)).first()
        if duplicate:
            row.status, row.duplicate_of_id = "duplicate", duplicate.id; self.db.commit(); return row
        external_reference = print_order_external_reference(self.tenant_id, row.platform, row.external_order_number)
        existing_order = self.db.query(Order).filter(Order.tenant_id == self.tenant_id, Order.external_reference == external_reference).first()
        if existing_order:
            source = self.db.query(PrintOrderImport).filter(PrintOrderImport.tenant_id == self.tenant_id, PrintOrderImport.order_id == existing_order.id).first()
            row.status, row.duplicate_of_id = "duplicate", source.id if source else None
            self.db.commit()
            return row
        idem = IdempotencyService(self.db, self.tenant_id).claim(key, "print-order.confirm", {"import_id": row.id})
        if idem.replay_resource_id:
            row.order_id = idem.replay_resource_id; row.status = "imported"; self.db.commit(); return row
        product_rows = {p.id: p for p in self.db.query(Product).filter(Product.tenant_id == self.tenant_id, Product.active.is_(True)).all()}
        if not {i.product_id for i in items}.issubset(product_rows):
            raise DomainError("Um ou mais produtos mapeados nao existem ou estao inativos.", code="PrintOrderInvalidProduct")
        cart = []
        for i in items:
            product = product_rows[i.product_id]
            flavor_names = [str(name).strip() for name in (i.flavor_names or []) if str(name).strip()] or [product.name]
            flavor_products = []
            for flavor_name in flavor_names:
                normalized = normalize_print_text(flavor_name)
                flavor = next((candidate for candidate in product_rows.values() if normalize_print_text(candidate.name) == normalized), None)
                if flavor is None:
                    flavor = self.db.query(Product).filter(Product.tenant_id == self.tenant_id, Product.active.is_(True)).all()
                    flavor = next((candidate for candidate in flavor if normalize_print_text(candidate.name) == normalized), None)
                if flavor is None:
                    raise DomainError(f"Sabor '{flavor_name}' não foi mapeado no catálogo.", code="PrintOrderFlavorMappingRequired")
                flavor_products.append(flavor)
            if product.id not in {flavor.id for flavor in flavor_products}:
                raise DomainError("A composição deve conter o produto principal mapeado.", code="PrintOrderPrimaryFlavorRequired")
            flavors = [FlavorIn(product_id=flavor.id, name=flavor.name, price=float(flavor.price), icon=flavor.icon or "") for flavor in flavor_products]
            customizations = i.customizations or {}

            def option_id(model, value, label):
                if not value:
                    return None
                resolved = self.db.query(model).filter(model.id == value, model.tenant_id == self.tenant_id, model.product_id == product.id, model.active.is_(True)).first()
                if resolved is None:
                    raise DomainError(f"{label} nao foi resolvido por um ID ativo do produto.", code="PrintOrderCompositionOptionNotResolved")
                return resolved.id

            selected_size_id = option_id(ProductSize, customizations.get("selected_size_id"), "Tamanho")
            if not selected_size_id and i.selected_size:
                size_matches = [size for size in getattr(product, "sizes", []) if size.active and normalize_print_text(size.label) == normalize_print_text(i.selected_size)]
                if len(size_matches) == 1:
                    selected_size_id = size_matches[0].id
                elif len(size_matches) > 1:
                    raise DomainError("O tamanho impresso possui mais de uma correspondencia no catalogo.", code="PrintOrderCompositionOptionNotResolved")

            addon_ids = customizations.get("add_on_ids", customizations.get("addon_ids", []))
            add_ons = []
            if addon_ids:
                if not isinstance(addon_ids, list) or any(not isinstance(value, str) for value in addon_ids):
                    raise DomainError("Adicionais devem ser informados por IDs do catalogo.", code="PrintOrderCompositionOptionNotResolved")
                addon_rows = self.db.query(InventoryRecipeVersion).filter(InventoryRecipeVersion.tenant_id == self.tenant_id, InventoryRecipeVersion.product_id == product.id, InventoryRecipeVersion.id.in_(addon_ids), InventoryRecipeVersion.component_role == "addon", InventoryRecipeVersion.active.is_(True), InventoryRecipeVersion.complement_key.isnot(None)).all()
                by_id = {addon.id: addon for addon in addon_rows}
                if len(by_id) != len(set(addon_ids)):
                    raise DomainError("Um ou mais adicionais nao foram resolvidos por IDs ativos do produto.", code="PrintOrderCompositionOptionNotResolved")
                add_ons = [by_id[value].complement_key for value in addon_ids]

            cart.append(build_print_order_cart_item(i, list(product_rows.values()), selected_size_id=selected_size_id, selected_crust_type_id=option_id(ProductCrustType, customizations.get("selected_crust_type_id"), "Massa"), selected_border_id=option_id(ProductCrustType, customizations.get("selected_border_id"), "Borda"), selected_drink_variant_id=option_id(ProductDrinkVariant, customizations.get("selected_drink_variant_id"), "Variante"), add_ons=add_ons, option_selections=customizations.get("option_selections", [])))
        delivery = DeliveryAddressIn(name=payload["customer_name"], phone=payload["customer_phone"], street=payload.get("delivery_street") or "Retirada", city=payload["delivery_city"], complement=payload.get("delivery_complement"), is_pickup=payload.get("fulfillment_type") == "pickup")
        try:
            # The canonical OrderService recalculates catalog/shipping values. The
            # partner receipt totals remain in the import reconciliation payload;
            # do not pass them as expected_total because that would conflate
            # partner-funded promotions with the ERP catalog total.
            order = OrderService(self.db, self.tenant_context).create_from_checkout(CheckoutIn(items=cart, delivery=delivery, payment_method=payload["payment_method"]), sales_channel="counter", order_origin=row.platform, partner_order_number=row.external_order_number, payment_status="pending", payment_source="manual", external_reference_override=external_reference, created_by_admin_id=self.admin_id)
            from datetime import datetime, timezone
            row.order_id, row.status, row.confirmed_by_admin_id, row.confirmed_at = order.id, "imported", self.admin_id, datetime.now(timezone.utc)
            self.db.commit(); IdempotencyService(self.db, self.tenant_id).complete(idem.record, order.id); self.db.refresh(row); return row
        except DomainError:
            self.db.rollback(); IdempotencyService(self.db, self.tenant_id).abandon(idem.record); raise
        except IntegrityError:
            self.db.rollback()
            existing_order = self.db.query(Order).filter(Order.tenant_id == self.tenant_id, Order.external_reference == external_reference).first()
            if existing_order:
                current = self._get(import_id)
                source = self.db.query(PrintOrderImport).filter(PrintOrderImport.tenant_id == self.tenant_id, PrintOrderImport.order_id == existing_order.id).first()
                current.status, current.duplicate_of_id = "duplicate", source.id if source else None
                self.db.commit()
                IdempotencyService(self.db, self.tenant_id).recover_completed(key, "print-order.confirm", {"import_id": import_id}, existing_order.id)
                return current
            IdempotencyService(self.db, self.tenant_id).abandon(idem.record)
            raise DomainError("A confirmacao concorrente falhou sem pedido recuperavel; tente novamente.", code="PrintOrderConcurrentConfirmation")

    def mapping(self, body: PrintOrderMappingIn) -> PrintOrderCatalogMapping:
        product = self.db.query(Product).filter(Product.id == body.product_id, Product.tenant_id == self.tenant_id, Product.active.is_(True)).first()
        if not product: raise DomainError("Produto nao encontrado ou inativo.", code="PrintOrderInvalidProduct")
        normalized = normalize_print_text(body.external_name)
        row = self.db.query(PrintOrderCatalogMapping).filter_by(tenant_id=self.tenant_id, platform=body.platform, normalized_external_name=normalized).first()
        if row is None: row = PrintOrderCatalogMapping(id=str(uuid.uuid4()), tenant_id=self.tenant_id, platform=body.platform, normalized_external_name=normalized, created_by_admin_id=self.admin_id); self.db.add(row)
        row.external_name, row.external_product_id, row.product_id, row.variation, row.status = body.external_name.strip(), body.external_product_id, body.product_id, body.variation, "approved"
        self.db.commit(); self.db.refresh(row); return row

    def serialize(self, row: PrintOrderImport) -> dict:
        payload = row.normalized_payload or {}
        return {"id": row.id, "tenant_id": row.tenant_id, "platform": row.platform, "external_order_number": row.external_order_number, "status": row.status, "source_asset_id": row.source_asset_id, "order_id": row.order_id, "duplicate_of_id": row.duplicate_of_id, "parser_version": row.parser_version, "review_notes": row.review_notes or [], "customer_name": payload.get("customer_name"), "customer_phone": payload.get("customer_phone"), "delivery_street": payload.get("delivery_street"), "delivery_city": payload.get("delivery_city"), "delivery_complement": payload.get("delivery_complement"), "fulfillment_type": payload.get("fulfillment_type"), "payment_method": payload.get("payment_method"), "printed_total": payload.get("printed_total"), "financials": payload.get("financials") or {}, "reconciliation": payload.get("reconciliation") or {}, "items": [{"id": i.id, "external_name": i.external_name, "product_id": i.product_id, "quantity": i.quantity, "selected_size": i.selected_size, "flavor_names": i.flavor_names or [], "unit_price": i.unit_price, "total_price": i.total_price, "match_status": i.match_status, "match_reason": i.match_reason} for i in self._items(row.id)], "created_at": row.created_at}
