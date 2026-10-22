"""Small, deterministic NF-e/NFC-e XML reader.

This parser deliberately uses only the standard library and rejects DTD,
entity, and oversized input before parsing.  It extracts identity evidence;
it does not validate a SEFAZ signature or authorize a document.
"""
from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime


MAX_XML_BYTES = 5 * 1024 * 1024
_FORBIDDEN_XML = re.compile(rb"<!\s*(?:DOCTYPE|ENTITY)", re.IGNORECASE)


class ReceiptXmlError(ValueError):
    """Input cannot be safely parsed as an inbound fiscal XML document."""


@dataclass(frozen=True)
class ReceiptXmlIdentity:
    content_sha256: str
    document_model: str
    access_key: str | None
    series: str | None
    number: str | None
    issuer_document: str | None
    issued_at: datetime | None
    extracted: dict


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _first(root: ET.Element, name: str) -> ET.Element | None:
    return next((node for node in root.iter() if _local(node.tag) == name), None)


def _value(root: ET.Element, name: str) -> str | None:
    node = _first(root, name)
    value = (node.text or "").strip() if node is not None else ""
    return value or None


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReceiptXmlError("dhEmi invalido no XML fiscal.") from exc


def parse_receipt_xml(raw_xml: bytes | str) -> ReceiptXmlIdentity:
    raw = raw_xml.encode("utf-8") if isinstance(raw_xml, str) else bytes(raw_xml)
    if not raw or len(raw) > MAX_XML_BYTES:
        raise ReceiptXmlError("XML ausente ou acima do limite de 5 MiB.")
    if _FORBIDDEN_XML.search(raw):
        raise ReceiptXmlError("DTD e entidades nao sao aceitos no XML fiscal.")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ReceiptXmlError("XML fiscal malformado.") from exc
    root_name = _local(root.tag)
    if root_name not in {"NFe", "nfeProc"}:
        raise ReceiptXmlError("A raiz deve ser NFe ou nfeProc.")
    inf = _first(root, "infNFe")
    if inf is None:
        raise ReceiptXmlError("XML fiscal sem infNFe.")
    access_key = (inf.attrib.get("Id") or "").removeprefix("NFe-") or None
    ide = _first(inf, "ide")
    if ide is None:
        ide = inf
    emit = _first(inf, "emit")
    model = _value(ide, "mod") or "55"
    if model not in {"55", "65"}:
        raise ReceiptXmlError("Modelo fiscal deve ser 55 (NFe) ou 65 (NFCe).")
    document_model = "NFCe" if model == "65" else "NFe"
    if access_key is not None and (not access_key.isdigit() or len(access_key) != 44):
        raise ReceiptXmlError("chNFe/Id deve conter a chave de acesso de 44 digitos.")
    extracted = {
        "model": model,
        "series": _value(ide, "serie"),
        "number": _value(ide, "nNF"),
        "issuer_document": _value(emit, "CNPJ") if emit is not None else None,
        "issued_at": _value(ide, "dhEmi") or _value(ide, "dEmi"),
    }
    return ReceiptXmlIdentity(
        content_sha256=hashlib.sha256(raw).hexdigest(),
        document_model=document_model,
        access_key=access_key,
        series=extracted["series"],
        number=extracted["number"],
        issuer_document=extracted["issuer_document"],
        issued_at=_parse_date(extracted["issued_at"]),
        extracted=extracted,
    )
