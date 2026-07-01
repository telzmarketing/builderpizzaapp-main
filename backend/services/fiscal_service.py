from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date, datetime, timezone
from html import escape

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from backend.core.exceptions import DomainError
from backend.models.fiscal import (
    FiscalCertificate,
    FiscalCompany,
    FiscalDocument,
    FiscalDocumentEvent,
    FiscalDocumentItem,
    FiscalProductProfile,
    FiscalSeries,
)
from backend.models.gestao import GestaoModuleSettings
from backend.models.order import Order, OrderItem
from backend.models.product import Product
from backend.schemas.fiscal import (
    FiscalCancelIn,
    FiscalCertificateIn,
    FiscalCompanyIn,
    FiscalDocumentFromOrderIn,
    FiscalInvalidateIn,
    FiscalProductProfileIn,
    FiscalSeriesIn,
)

TENANT_ID = "default"


class FiscalNotFound(DomainError):
    http_status = 404

    def __init__(self, entity: str):
        super().__init__(f"{entity} fiscal nao encontrado.", code="FiscalNotFound")


class FiscalInvalidOperation(DomainError):
    def __init__(self, message: str):
        super().__init__(message, code="FiscalInvalidOperation")


class FiscalService:
    def __init__(self, db: Session, tenant_id: str = TENANT_ID):
        self._db = db
        self._tenant_id = tenant_id

    def overview(self) -> dict:
        documents = self.list_documents()
        counts: dict[str, int] = {}
        for item in documents:
            counts[item["status"]] = counts.get(item["status"], 0) + 1
        missing = self._missing_setup()
        return {
            "company": self._serialize_company(self._company()) if self._company() else None,
            "certificate": self._serialize_certificate(self._certificate()) if self._certificate() else None,
            "series": self.list_series(),
            "product_profiles": self.list_product_profiles(),
            "documents": documents,
            "document_status_counts": counts,
            "ready_for_homologation": not missing,
            "missing_setup": missing,
        }

    def upsert_company(self, payload: FiscalCompanyIn) -> dict:
        row = self._company()
        data = payload.model_dump()
        if row:
            for key, value in data.items():
                setattr(row, key, value)
        else:
            row = FiscalCompany(id=f"fis-comp-{uuid.uuid4().hex[:12]}", tenant_id=self._tenant_id, **data)
            self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return self._serialize_company(row)

    def upsert_certificate(self, payload: FiscalCertificateIn) -> dict:
        row = self._certificate()
        data = payload.model_dump()
        if row:
            for key, value in data.items():
                setattr(row, key, value)
        else:
            row = FiscalCertificate(id=f"fis-cert-{uuid.uuid4().hex[:12]}", tenant_id=self._tenant_id, **data)
            self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return self._serialize_certificate(row)

    def list_series(self) -> list[dict]:
        rows = (
            self._db.query(FiscalSeries)
            .filter(FiscalSeries.tenant_id == self._tenant_id)
            .order_by(FiscalSeries.document_model, FiscalSeries.environment, FiscalSeries.series)
            .all()
        )
        return [self._serialize_series(row) for row in rows]

    def create_series(self, payload: FiscalSeriesIn) -> dict:
        row = FiscalSeries(id=f"fis-ser-{uuid.uuid4().hex[:12]}", tenant_id=self._tenant_id, **payload.model_dump())
        self._db.add(row)
        try:
            self._db.commit()
        except IntegrityError:
            self._db.rollback()
            raise FiscalInvalidOperation("Serie fiscal ja cadastrada para este modelo e ambiente.")
        self._db.refresh(row)
        return self._serialize_series(row)

    def update_series(self, series_id: str, payload: FiscalSeriesIn) -> dict:
        row = self._get_series(series_id)
        for key, value in payload.model_dump().items():
            setattr(row, key, value)
        self._db.commit()
        self._db.refresh(row)
        return self._serialize_series(row)

    def list_product_profiles(self) -> list[dict]:
        rows = (
            self._db.query(FiscalProductProfile)
            .options(joinedload(FiscalProductProfile.product))
            .filter(FiscalProductProfile.tenant_id == self._tenant_id)
            .order_by(FiscalProductProfile.created_at.desc())
            .all()
        )
        return [self._serialize_profile(row) for row in rows]

    def upsert_product_profile(self, product_id: str, payload: FiscalProductProfileIn) -> dict:
        if product_id != payload.product_id:
            raise FiscalInvalidOperation("Produto da URL precisa ser o mesmo do perfil fiscal.")
        product = self._db.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise FiscalNotFound("Produto")
        row = (
            self._db.query(FiscalProductProfile)
            .filter(FiscalProductProfile.tenant_id == self._tenant_id, FiscalProductProfile.product_id == product_id)
            .first()
        )
        data = payload.model_dump()
        if row:
            for key, value in data.items():
                setattr(row, key, value)
        else:
            row = FiscalProductProfile(id=f"fis-prof-{uuid.uuid4().hex[:12]}", tenant_id=self._tenant_id, **data)
            self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return self._serialize_profile(row)

    def list_documents(self) -> list[dict]:
        rows = (
            self._db.query(FiscalDocument)
            .options(joinedload(FiscalDocument.items), joinedload(FiscalDocument.events))
            .filter(FiscalDocument.tenant_id == self._tenant_id)
            .order_by(FiscalDocument.created_at.desc())
            .limit(200)
            .all()
        )
        return [self._serialize_document(row, include_xml=False) for row in rows]

    def create_document_from_order(self, order_id: str, payload: FiscalDocumentFromOrderIn) -> dict:
        settings = self._module_settings()
        if not settings:
            raise FiscalInvalidOperation("Modulo fiscal precisa estar habilitado para gerar documento.")

        company = self._company()
        if not company:
            raise FiscalInvalidOperation("Cadastre os dados fiscais da empresa antes de gerar documento.")
        order = (
            self._db.query(Order)
            .options(joinedload(Order.items).joinedload(OrderItem.flavors))
            .filter(Order.id == order_id)
            .first()
        )
        if not order:
            raise FiscalNotFound("Pedido")
        existing = (
            self._db.query(FiscalDocument)
            .filter(FiscalDocument.tenant_id == self._tenant_id, FiscalDocument.order_id == order_id)
            .first()
        )
        if existing:
            return self._serialize_document(existing)

        series = self._resolve_series(payload)
        issue_date = datetime.now(timezone.utc)
        number = series.next_number
        series.next_number += 1
        items_payload = self._order_items_snapshot(order)
        total_products = round(sum(float(item["total_price"] or 0.0) for item in items_payload), 2)
        total_shipping = round(float(order.delivery_fee_final or order.shipping_fee or 0.0), 2)
        total_discount = round(float(order.discount or 0.0) + float(order.delivery_fee_discount or 0.0), 2)
        total_document = round(float(order.total or 0.0), 2)
        access_key = self._build_access_key(company, series, number, issue_date)
        snapshot = {
            "order_id": order.id,
            "order_code": order.order_code,
            "sales_channel": order.sales_channel,
            "customer_name": order.delivery_name,
            "totals": {
                "products": total_products,
                "shipping": total_shipping,
                "discount": total_discount,
                "document": total_document,
            },
            "items": items_payload,
        }
        row = FiscalDocument(
            id=f"fis-doc-{uuid.uuid4().hex[:12]}",
            tenant_id=self._tenant_id,
            order_id=order.id,
            company_id=company.id,
            series_id=series.id,
            document_model=series.document_model,
            environment=series.environment,
            status="validated",
            operation_type="sale",
            series=series.series,
            number=number,
            access_key=access_key,
            issue_date=issue_date,
            customer_name=order.delivery_name,
            customer_document=None,
            total_products=total_products,
            total_shipping=total_shipping,
            total_discount=total_discount,
            total_document=total_document,
            snapshot_json=json.dumps(snapshot, ensure_ascii=False),
        )
        self._db.add(row)
        self._db.flush()
        for item in items_payload:
            self._db.add(FiscalDocumentItem(
                id=f"fis-itm-{uuid.uuid4().hex[:12]}",
                document_id=row.id,
                **item,
            ))
        row.xml_content = self._build_xml(row, company, items_payload)
        self._record_event(row, "create", "validated", "Documento fiscal preparado em ambiente interno.")
        self._db.commit()
        self._db.refresh(row)
        return self._serialize_document(row)

    def sign_document(self, document_id: str) -> dict:
        row = self._get_document(document_id)
        if row.status not in {"draft", "validated"}:
            raise FiscalInvalidOperation("Somente documento em rascunho/validado pode ser assinado.")
        cert = self._certificate()
        if not cert or not self._certificate_valid(cert):
            self._record_event(row, "sign", "blocked", "Certificado A1 valido nao configurado.")
            self._db.commit()
            raise FiscalInvalidOperation("Configure um certificado A1 valido antes de assinar.")
        if not row.xml_content:
            raise FiscalInvalidOperation("Documento sem XML para assinatura.")
        digest = hashlib.sha256(row.xml_content.encode("utf-8")).hexdigest()
        row.signed_xml_content = row.xml_content.replace("</FiscalDocumentDraft>", f"<SignatureDigest>{digest}</SignatureDigest></FiscalDocumentDraft>")
        row.status = "signed"
        self._record_event(row, "sign", "signed", "Documento marcado como assinado pela camada fiscal interna.")
        self._db.commit()
        self._db.refresh(row)
        return self._serialize_document(row)

    def transmit_document(self, document_id: str) -> dict:
        row = self._get_document(document_id)
        if row.status != "signed":
            raise FiscalInvalidOperation("Somente documento assinado pode ser transmitido.")
        settings = self._module_settings()
        if not settings.get("sefaz_integration_enabled"):
            self._record_event(row, "transmit", "blocked", "Integracao SEFAZ direta desabilitada.")
            self._db.commit()
            raise FiscalInvalidOperation("Habilite a integracao SEFAZ direta para transmitir.")
        row.status = "transmitting"
        self._record_event(row, "transmit", "queued", "Documento pronto para envio ao webservice SEFAZ direto.")
        self._db.commit()
        self._db.refresh(row)
        return self._serialize_document(row)

    def consult_document(self, document_id: str) -> dict:
        row = self._get_document(document_id)
        self._record_event(row, "consult", "recorded", "Consulta registrada. Cliente SEFAZ direto ainda nao executado neste ambiente.")
        self._db.commit()
        self._db.refresh(row)
        return self._serialize_document(row)

    def cancel_document(self, document_id: str, payload: FiscalCancelIn) -> dict:
        row = self._get_document(document_id)
        if row.status != "authorized":
            raise FiscalInvalidOperation("Somente documento autorizado pode ser cancelado.")
        row.status = "cancel_pending"
        self._record_event(row, "cancel", "pending", payload.reason)
        self._db.commit()
        self._db.refresh(row)
        return self._serialize_document(row)

    def invalidate_number(self, series_id: str, payload: FiscalInvalidateIn) -> dict:
        series = self._get_series(series_id)
        row = FiscalDocument(
            id=f"fis-doc-{uuid.uuid4().hex[:12]}",
            tenant_id=self._tenant_id,
            series_id=series.id,
            document_model=series.document_model,
            environment=series.environment,
            status="inutilized",
            operation_type="inutilization",
            series=series.series,
            number=payload.number,
            issue_date=datetime.now(timezone.utc),
            total_products=0.0,
            total_shipping=0.0,
            total_discount=0.0,
            total_document=0.0,
            snapshot_json=json.dumps({"reason": payload.reason}, ensure_ascii=False),
        )
        self._db.add(row)
        self._db.flush()
        self._record_event(row, "inutilize", "recorded", payload.reason)
        self._db.commit()
        self._db.refresh(row)
        return self._serialize_document(row)

    def _company(self) -> FiscalCompany | None:
        return (
            self._db.query(FiscalCompany)
            .filter(FiscalCompany.tenant_id == self._tenant_id, FiscalCompany.active == True)
            .order_by(FiscalCompany.updated_at.desc())
            .first()
        )

    def _certificate(self) -> FiscalCertificate | None:
        return (
            self._db.query(FiscalCertificate)
            .filter(FiscalCertificate.tenant_id == self._tenant_id, FiscalCertificate.active == True)
            .order_by(FiscalCertificate.updated_at.desc())
            .first()
        )

    def _module_settings(self) -> dict:
        item = (
            self._db.query(GestaoModuleSettings)
            .filter(GestaoModuleSettings.tenant_id == self._tenant_id, GestaoModuleSettings.module_key == "fiscal")
            .first()
        )
        if not item or not item.enabled or item.status == "disabled":
            return {}
        try:
            return json.loads(item.settings_json or "{}")
        except json.JSONDecodeError:
            return {}

    def _missing_setup(self) -> list[str]:
        missing: list[str] = []
        company = self._company()
        cert = self._certificate()
        if not company:
            missing.append("company")
        if not cert or not self._certificate_valid(cert):
            missing.append("certificate")
        if not self.list_series():
            missing.append("series")
        return missing

    def _certificate_valid(self, cert: FiscalCertificate) -> bool:
        today = date.today()
        return bool(cert.active and cert.password_configured and cert.valid_until and cert.valid_until >= today)

    def _resolve_series(self, payload: FiscalDocumentFromOrderIn) -> FiscalSeries:
        if payload.series_id:
            row = self._get_series(payload.series_id)
            if row.document_model != payload.document_model or row.environment != payload.environment:
                raise FiscalInvalidOperation("Serie nao corresponde ao modelo/ambiente informado.")
            return row
        row = (
            self._db.query(FiscalSeries)
            .filter(
                FiscalSeries.tenant_id == self._tenant_id,
                FiscalSeries.document_model == payload.document_model,
                FiscalSeries.environment == payload.environment,
                FiscalSeries.active == True,
            )
            .order_by(FiscalSeries.series)
            .first()
        )
        if not row:
            raise FiscalInvalidOperation("Cadastre uma serie fiscal ativa para o modelo e ambiente.")
        return row

    def _get_series(self, series_id: str) -> FiscalSeries:
        row = (
            self._db.query(FiscalSeries)
            .filter(FiscalSeries.tenant_id == self._tenant_id, FiscalSeries.id == series_id)
            .first()
        )
        if not row:
            raise FiscalNotFound("Serie")
        return row

    def _get_document(self, document_id: str) -> FiscalDocument:
        row = (
            self._db.query(FiscalDocument)
            .options(joinedload(FiscalDocument.items), joinedload(FiscalDocument.events))
            .filter(FiscalDocument.tenant_id == self._tenant_id, FiscalDocument.id == document_id)
            .first()
        )
        if not row:
            raise FiscalNotFound("Documento")
        return row

    def _order_items_snapshot(self, order: Order) -> list[dict]:
        product_ids = {item.product_id for item in order.items}
        products = {row.id: row for row in self._db.query(Product).filter(Product.id.in_(product_ids)).all()} if product_ids else {}
        profiles = {
            row.product_id: row
            for row in self._db.query(FiscalProductProfile)
            .filter(FiscalProductProfile.tenant_id == self._tenant_id, FiscalProductProfile.product_id.in_(product_ids), FiscalProductProfile.active == True)
            .all()
        } if product_ids else {}
        rows: list[dict] = []
        for item in order.items:
            product = products.get(item.product_id)
            profile = profiles.get(item.product_id)
            if not profile:
                raise FiscalInvalidOperation(f"Produto sem perfil tributario: {product.name if product else item.product_id}.")
            profile_data = self._profile_snapshot(profile)
            rows.append({
                "product_id": item.product_id,
                "description": profile.fiscal_description or (product.name if product else "Produto"),
                "quantity": float(item.quantity or 1),
                "unit_price": round(float(item.unit_price or 0.0), 2),
                "total_price": round(float(item.total_price or 0.0), 2),
                "ncm": profile.ncm,
                "cest": profile.cest,
                "cfop": profile.cfop,
                "origin": profile.origin,
                "cst": profile.cst,
                "csosn": profile.csosn,
                "icms_rate": profile.icms_rate,
                "pis_cst": profile.pis_cst,
                "pis_rate": profile.pis_rate,
                "cofins_cst": profile.cofins_cst,
                "cofins_rate": profile.cofins_rate,
                "tax_profile_snapshot_json": json.dumps(profile_data, ensure_ascii=False),
            })
        return rows

    def _profile_snapshot(self, row: FiscalProductProfile) -> dict:
        return {
            "ncm": row.ncm,
            "cest": row.cest,
            "cfop": row.cfop,
            "origin": row.origin,
            "cst": row.cst,
            "csosn": row.csosn,
            "icms_rate": row.icms_rate,
            "pis_cst": row.pis_cst,
            "pis_rate": row.pis_rate,
            "cofins_cst": row.cofins_cst,
            "cofins_rate": row.cofins_rate,
        }

    def _build_access_key(self, company: FiscalCompany, series: FiscalSeries, number: int, issued_at: datetime) -> str:
        raw = f"{company.document}{series.document_model}{series.environment}{series.series}{number}{issued_at.isoformat()}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:44]

    def _build_xml(self, row: FiscalDocument, company: FiscalCompany, items: list[dict]) -> str:
        item_xml = "".join(
            f"<Item><Description>{escape(item['description'])}</Description><NCM>{escape(item['ncm'] or '')}</NCM>"
            f"<CFOP>{escape(item['cfop'] or '')}</CFOP><Quantity>{item['quantity']}</Quantity>"
            f"<UnitPrice>{item['unit_price']}</UnitPrice><Total>{item['total_price']}</Total></Item>"
            for item in items
        )
        return (
            "<FiscalDocumentDraft>"
            f"<Model>{escape(row.document_model)}</Model><Environment>{escape(row.environment)}</Environment>"
            f"<AccessKey>{escape(row.access_key or '')}</AccessKey><Series>{escape(row.series or '')}</Series><Number>{row.number}</Number>"
            f"<Issuer><LegalName>{escape(company.legal_name)}</LegalName><Document>{escape(company.document)}</Document>"
            f"<State>{escape(company.state or '')}</State><CityCode>{escape(company.city_ibge_code or '')}</CityCode></Issuer>"
            f"<Totals><Products>{row.total_products}</Products><Shipping>{row.total_shipping}</Shipping>"
            f"<Discount>{row.total_discount}</Discount><Document>{row.total_document}</Document></Totals>"
            f"<Items>{item_xml}</Items>"
            "</FiscalDocumentDraft>"
        )

    def _record_event(self, row: FiscalDocument, event_type: str, status: str, message: str, protocol: str | None = None) -> None:
        self._db.add(FiscalDocumentEvent(
            id=f"fis-evt-{uuid.uuid4().hex[:12]}",
            tenant_id=self._tenant_id,
            document_id=row.id,
            event_type=event_type,
            status=status,
            protocol=protocol,
            message=message,
        ))

    def _serialize_company(self, row: FiscalCompany) -> dict:
        return {column.name: getattr(row, column.name) for column in row.__table__.columns}

    def _serialize_certificate(self, row: FiscalCertificate) -> dict:
        data = {column.name: getattr(row, column.name) for column in row.__table__.columns}
        data["valid"] = self._certificate_valid(row)
        return data

    def _serialize_series(self, row: FiscalSeries) -> dict:
        return {column.name: getattr(row, column.name) for column in row.__table__.columns}

    def _serialize_profile(self, row: FiscalProductProfile) -> dict:
        data = {column.name: getattr(row, column.name) for column in row.__table__.columns}
        data["product_name"] = row.product.name if row.product else None
        return data

    def _serialize_document(self, row: FiscalDocument, include_xml: bool = True) -> dict:
        data = {column.name: getattr(row, column.name) for column in row.__table__.columns}
        if not include_xml:
            data["xml_content"] = None
            data["signed_xml_content"] = None
        data["items"] = [
            {column.name: getattr(item, column.name) for column in item.__table__.columns if column.name not in {"document_id", "tax_profile_snapshot_json"}}
            for item in row.items
        ]
        data["events"] = [
            {
                "id": event.id,
                "event_type": event.event_type,
                "status": event.status,
                "protocol": event.protocol,
                "message": event.message,
                "created_at": event.created_at,
            }
            for event in sorted(row.events, key=lambda item: item.created_at or datetime.min.replace(tzinfo=timezone.utc))
        ]
        return data
