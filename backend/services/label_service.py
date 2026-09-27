"""Deterministic browser-first label generation for the dispatch station."""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload
from fastapi.encoders import jsonable_encoder

from backend.core.exceptions import DomainError, OrderNotFound
from backend.core.tenant_context import TenantContext
from backend.models.label import (
    LabelPrinter, LabelPrinterTemplate, LabelPrintJob, LabelSetting,
    LabelTemplate, LabelVersion, LabelVolume, LabelVolumeRule,
)
from backend.models.order import Order, OrderItem
from backend.models.platform_saas import TenantProfile
from backend.models.product import Product
from backend.models.tenant import Tenant
from backend.schemas.label import (
    LabelPrinterIn, LabelPrintIn, LabelReprintIn, LabelSettingsIn,
    LabelTemplateIn, LabelVolumeRuleIn,
)


class LabelService:
    def __init__(self, db: Session, tenant_context: TenantContext):
        self.db = db
        self.tenant_id = tenant_context.tenant_id

    @staticmethod
    def _uuid() -> str:
        return str(uuid.uuid4())

    @staticmethod
    def _status(value) -> str:
        return value.value if hasattr(value, "value") else str(value)

    def _get(self, model, row_id: str, code: str):
        row = self.db.query(model).filter(model.id == row_id, model.tenant_id == self.tenant_id).first()
        if row is None:
            error = DomainError("Registro nao encontrado neste estabelecimento.", code=code)
            error.http_status = 404
            raise error
        return row

    def _commit(self, conflict_code="LabelConfigurationConflict"):
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise DomainError("Configuracao duplicada ou concorrente.", code=conflict_code) from exc

    def list_printers(self):
        self._ensure_defaults()
        return [self._printer(row) for row in self.db.query(LabelPrinter).filter(
            LabelPrinter.tenant_id == self.tenant_id
        ).order_by(LabelPrinter.name).all()]

    def save_printer(self, body: LabelPrinterIn, printer_id: str | None = None):
        row = self._get(LabelPrinter, printer_id, "LabelPrinterNotFound") if printer_id else LabelPrinter(
            id=self._uuid(), tenant_id=self.tenant_id
        )
        if not printer_id:
            self.db.add(row)
        if body.is_default:
            self.db.query(LabelPrinter).filter(LabelPrinter.tenant_id == self.tenant_id).update({"is_default": False})
        for key, value in body.model_dump().items():
            setattr(row, key, value)
        self._commit()
        self.db.refresh(row)
        return self._printer(row)

    def delete_printer(self, printer_id: str):
        row = self._get(LabelPrinter, printer_id, "LabelPrinterNotFound")
        self.db.delete(row)
        self._commit()
        return {"id": printer_id, "deleted": True}

    def list_templates(self):
        self._ensure_defaults()
        rows = self.db.query(LabelTemplate).filter(LabelTemplate.tenant_id == self.tenant_id).order_by(LabelTemplate.name).all()
        return [self._template(row) for row in rows]

    def save_template(self, body: LabelTemplateIn, template_id: str | None = None):
        row = self._get(LabelTemplate, template_id, "LabelTemplateNotFound") if template_id else LabelTemplate(
            id=self._uuid(), tenant_id=self.tenant_id
        )
        printer_ids = list(dict.fromkeys(body.printer_ids))
        if printer_ids:
            found = self.db.query(LabelPrinter.id).filter(
                LabelPrinter.tenant_id == self.tenant_id, LabelPrinter.id.in_(printer_ids)
            ).count()
            if found != len(printer_ids):
                raise DomainError("Uma impressora vinculada nao pertence ao estabelecimento.", code="LabelPrinterNotFound")
        if not template_id:
            self.db.add(row)
        if body.is_default:
            self.db.query(LabelTemplate).filter(LabelTemplate.tenant_id == self.tenant_id).update({"is_default": False})
        for key, value in body.model_dump(exclude={"printer_ids"}).items():
            setattr(row, key, value)
        self.db.flush()
        self.db.query(LabelPrinterTemplate).filter(
            LabelPrinterTemplate.tenant_id == self.tenant_id,
            LabelPrinterTemplate.template_id == row.id,
        ).delete(synchronize_session=False)
        for printer_id in printer_ids:
            self.db.add(LabelPrinterTemplate(
                id=self._uuid(), tenant_id=self.tenant_id,
                printer_id=printer_id, template_id=row.id,
            ))
        self._commit()
        self.db.refresh(row)
        return self._template(row)

    def delete_template(self, template_id: str):
        row = self._get(LabelTemplate, template_id, "LabelTemplateNotFound")
        self.db.delete(row)
        self._commit()
        return {"id": template_id, "deleted": True}

    def get_settings(self):
        self._ensure_defaults()
        row = self.db.query(LabelSetting).filter(LabelSetting.tenant_id == self.tenant_id).first()
        return self._settings(row)

    def save_settings(self, body: LabelSettingsIn):
        if body.default_printer_id:
            self._get(LabelPrinter, body.default_printer_id, "LabelPrinterNotFound")
        if body.default_template_id:
            self._get(LabelTemplate, body.default_template_id, "LabelTemplateNotFound")
        row = self.db.query(LabelSetting).filter(LabelSetting.tenant_id == self.tenant_id).first()
        if row is None:
            row = LabelSetting(tenant_id=self.tenant_id)
            self.db.add(row)
        for key, value in body.model_dump().items():
            setattr(row, key, value)
        self._commit()
        self.db.refresh(row)
        return self._settings(row)

    def list_rules(self):
        return [self._rule(row) for row in self.db.query(LabelVolumeRule).filter(
            LabelVolumeRule.tenant_id == self.tenant_id
        ).order_by(LabelVolumeRule.scope_type, LabelVolumeRule.scope_value).all()]

    def save_rule(self, body: LabelVolumeRuleIn, rule_id: str | None = None):
        if body.scope_type == "product":
            exists = self.db.query(Product.id).filter(Product.id == body.scope_value, Product.tenant_id == self.tenant_id).first()
            if not exists:
                raise DomainError("Produto nao encontrado neste estabelecimento.", code="LabelRuleProductNotFound")
        row = self._get(LabelVolumeRule, rule_id, "LabelVolumeRuleNotFound") if rule_id else LabelVolumeRule(
            id=self._uuid(), tenant_id=self.tenant_id
        )
        if not rule_id:
            self.db.add(row)
        for key, value in body.model_dump().items():
            setattr(row, key, value.strip() if key == "scope_value" else value)
        self._commit()
        self.db.refresh(row)
        return self._rule(row)

    def delete_rule(self, rule_id: str):
        row = self._get(LabelVolumeRule, rule_id, "LabelVolumeRuleNotFound")
        self.db.delete(row)
        self._commit()
        return {"id": rule_id, "deleted": True}

    def preview(self, order_id: str, *, printer_id: str | None = None, template_id: str | None = None):
        self._ensure_defaults()
        order = self.db.query(Order).options(joinedload(Order.items).joinedload(OrderItem.flavors)).filter(
            Order.id == order_id, Order.tenant_id == self.tenant_id
        ).first()
        if order is None:
            raise OrderNotFound(order_id)
        settings = self.db.query(LabelSetting).filter(LabelSetting.tenant_id == self.tenant_id).first()
        printer = self._resolve_printer(printer_id or (settings.default_printer_id if settings else None))
        template = self._resolve_template(template_id or (settings.default_template_id if settings else None), printer)
        products = self._products(order)
        tenant = self.db.query(Tenant).filter(Tenant.id == self.tenant_id).first()
        profile = self.db.query(TenantProfile).filter(TenantProfile.tenant_id == self.tenant_id).first()
        identity = {"name": (profile.trade_name if profile and profile.trade_name else tenant.name if tenant else ""),
                    "logo_url": profile.logo_url if profile else None}
        snapshot, raw_volumes = self._snapshot(
            order, products, include_drinks=bool(settings and settings.include_drinks), identity=identity,
        )
        fingerprint = hashlib.sha256(json.dumps(snapshot, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
        version = self.db.query(LabelVersion).filter(
            LabelVersion.tenant_id == self.tenant_id, LabelVersion.order_id == order.id,
            LabelVersion.fingerprint == fingerprint, LabelVersion.invalidated_at.is_(None),
        ).first()
        if version is None:
            now = datetime.now(timezone.utc)
            self.db.query(LabelVersion).filter(
                LabelVersion.tenant_id == self.tenant_id, LabelVersion.order_id == order.id,
                LabelVersion.invalidated_at.is_(None),
            ).update({"invalidated_at": now}, synchronize_session=False)
            number = (self.db.query(func.max(LabelVersion.version_number)).filter(
                LabelVersion.tenant_id == self.tenant_id, LabelVersion.order_id == order.id
            ).scalar() or 0) + 1
            version = LabelVersion(
                id=self._uuid(), tenant_id=self.tenant_id, order_id=order.id,
                version_number=number, fingerprint=fingerprint, snapshot_json=snapshot,
            )
            self.db.add(version)
            self.db.flush()
            for raw in raw_volumes:
                self.db.add(LabelVolume(
                    id=self._uuid(), tenant_id=self.tenant_id, label_version_id=version.id,
                    order_item_id=raw["order_item_id"], sequence=raw["sequence"],
                    total_volumes=len(raw_volumes), unit_index=raw["unit_index"],
                    volume_index=raw["volume_index"], content_json=raw["content"],
                ))
            self._commit("LabelVersionConcurrencyConflict")
            self.db.refresh(version)
        volumes = self.db.query(LabelVolume).filter(
            LabelVolume.tenant_id == self.tenant_id, LabelVolume.label_version_id == version.id
        ).order_by(LabelVolume.sequence).all()
        previous_count = self.db.query(LabelPrintJob).filter(
            LabelPrintJob.tenant_id == self.tenant_id, LabelPrintJob.order_id == order.id,
            LabelPrintJob.job_type.in_(("print", "reprint")),
        ).count()
        return {
            "order": {"id": order.id, "order_code": order.order_code, "status": self._status(order.status),
                      "fulfillment_type": order.fulfillment_type, "customer_name": order.delivery_name, "notes": order.notes},
            "restaurant": identity,
            "version": {"id": version.id, "number": version.version_number, "fingerprint": version.fingerprint,
                        "created_at": version.created_at, "invalidated_at": version.invalidated_at},
            "printer": self._printer(printer) if printer else None,
            "template": self._template(template) if template else None,
            "volumes": [{"id": row.id, "sequence": row.sequence, "total_volumes": row.total_volumes,
                         "order_item_id": row.order_item_id, "unit_index": row.unit_index,
                         "volume_index": row.volume_index, **row.content_json} for row in volumes],
            "volume_count": len(volumes), "is_first_print": previous_count == 0,
            "previous_print_count": previous_count,
        }

    def request_print(self, order_id: str, body: LabelPrintIn | LabelReprintIn, *, actor_id: str, reprint: bool):
        existing = self.db.query(LabelPrintJob).filter(
            LabelPrintJob.tenant_id == self.tenant_id, LabelPrintJob.idempotency_key == body.idempotency_key
        ).first()
        if existing:
            if existing.order_id != order_id or existing.job_type != ("reprint" if reprint else "print"):
                raise DomainError("Chave de idempotencia ja usada em outra operacao.", code="LabelIdempotencyConflict")
            return {"job": self._job(existing), "preview": self.preview(order_id, printer_id=existing.printer_id, template_id=existing.template_id)}
        preview = self.preview(order_id, printer_id=body.printer_id, template_id=body.template_id)
        settings = self.db.query(LabelSetting).filter(LabelSetting.tenant_id == self.tenant_id).first()
        if reprint and (settings is None or settings.require_reprint_reason) and not getattr(body, "reason", None):
            raise DomainError("Informe o motivo da reimpressao.", code="LabelReprintReasonRequired")
        if reprint and preview["previous_print_count"] == 0:
            raise DomainError("Nao existe impressao anterior para reimprimir.", code="LabelFirstPrintRequired")
        if not reprint and preview["previous_print_count"] > 0:
            raise DomainError("Pedido ja impresso; use a operacao de reimpressao.", code="LabelReprintRequired")
        job = LabelPrintJob(
            id=self._uuid(), tenant_id=self.tenant_id, order_id=order_id,
            label_version_id=preview["version"]["id"],
            printer_id=preview["printer"]["id"] if preview["printer"] else None,
            template_id=preview["template"]["id"] if preview["template"] else None,
            actor_id=actor_id, job_type="reprint" if reprint else "print",
            idempotency_key=body.idempotency_key, copies=body.copies,
            reason=getattr(body, "reason", None), result_status="requested",
            snapshot_json=jsonable_encoder(preview),
        )
        self.db.add(job)
        self._commit("LabelPrintConcurrencyConflict")
        self.db.refresh(job)
        return {"job": self._job(job), "preview": preview}

    def history(self, order_id: str):
        if not self.db.query(Order.id).filter(Order.id == order_id, Order.tenant_id == self.tenant_id).first():
            raise OrderNotFound(order_id)
        return [self._job(row) for row in self.db.query(LabelPrintJob).filter(
            LabelPrintJob.tenant_id == self.tenant_id, LabelPrintJob.order_id == order_id
        ).order_by(LabelPrintJob.created_at.desc()).all()]

    def request_test(self, body: LabelPrintIn, *, actor_id: str):
        existing = self.db.query(LabelPrintJob).filter(
            LabelPrintJob.tenant_id == self.tenant_id, LabelPrintJob.idempotency_key == body.idempotency_key
        ).first()
        if existing:
            return {"job": self._job(existing), "preview": existing.snapshot_json}
        printer = self._resolve_printer(body.printer_id)
        template = self._resolve_template(body.template_id, printer)
        now = datetime.now(timezone.utc)
        template_data = self._template(template)
        snapshot = {
            "test": True,
            "printer": self._printer(printer),
            "template": template_data,
            "content": {"title": "ETIQUETA DE TESTE", "large_number": "123", "generated_at": now.isoformat()},
            "print_area": {
                "width_mm": template.width_mm,
                "height_mm": template.height_mm,
                "dpi": template.dpi,
                "margins_mm": {"top": template.margin_top_mm, "right": template.margin_right_mm,
                               "bottom": template.margin_bottom_mm, "left": template.margin_left_mm},
                "safe_area_mm": template.safe_area_mm,
                "offset_x_mm": template.offset_x_mm,
                "offset_y_mm": template.offset_y_mm,
            },
        }
        job = LabelPrintJob(
            id=self._uuid(), tenant_id=self.tenant_id, actor_id=actor_id, job_type="test",
            printer_id=printer.id if printer else None, template_id=template.id if template else None,
            idempotency_key=body.idempotency_key, copies=body.copies,
            result_status="requested", snapshot_json=jsonable_encoder(snapshot),
        )
        self.db.add(job)
        self._commit("LabelPrintConcurrencyConflict")
        self.db.refresh(job)
        return {"job": self._job(job), "preview": snapshot}

    def mark_dialog_opened(self, job_id: str, *, actor_id: str):
        job = self._get(LabelPrintJob, job_id, "LabelPrintJobNotFound")
        if job.actor_id != actor_id:
            raise DomainError("Somente o operador solicitante pode confirmar a abertura do dialogo.", code="LabelPrintActorMismatch")
        job.result_status = "dialog_opened"
        self._commit()
        self.db.refresh(job)
        return self._job(job)

    def _resolve_printer(self, printer_id):
        if printer_id:
            row = self._get(LabelPrinter, printer_id, "LabelPrinterNotFound")
            if not row.active:
                raise DomainError("Impressora inativa.", code="LabelPrinterInactive")
            return row
        row = self.db.query(LabelPrinter).filter(
            LabelPrinter.tenant_id == self.tenant_id, LabelPrinter.active.is_(True)
        ).order_by(LabelPrinter.is_default.desc(), LabelPrinter.name).first()
        if row is None:
            raise DomainError("Configure uma impressora logica antes de gerar etiquetas.", code="LabelPrinterNotConfigured")
        return row

    def _ensure_defaults(self):
        """Idempotently provision browser-first defaults for tenants created after migration."""
        digest = hashlib.md5(self.tenant_id.encode(), usedforsecurity=False).hexdigest()
        printer_id = f"label-browser-{digest}"
        template_id = f"label-template-{digest}"
        if self.db.query(LabelSetting.tenant_id).filter(LabelSetting.tenant_id == self.tenant_id).first():
            return
        printer = self.db.query(LabelPrinter).filter(
            LabelPrinter.id == printer_id, LabelPrinter.tenant_id == self.tenant_id
        ).first()
        if printer is None:
            printer = LabelPrinter(
                id=printer_id, tenant_id=self.tenant_id, name="Impressao pelo navegador",
                description="Fila fisica escolhida no dialogo do sistema operacional",
                printer_type="thermal", connection_type="browser", max_width_mm=100,
                sector="dispatch", dpi=203, active=True, is_default=True,
            )
            self.db.add(printer)
        template = self.db.query(LabelTemplate).filter(
            LabelTemplate.id == template_id, LabelTemplate.tenant_id == self.tenant_id
        ).first()
        if template is None:
            template = LabelTemplate(
                id=template_id, tenant_id=self.tenant_id, name="Padrao 100x50 mm",
                label_type="gap",
                width_mm=100, height_mm=50, margin_top_mm=2, margin_right_mm=2,
                margin_bottom_mm=2, margin_left_mm=2, safe_area_mm=1, gap_mm=2,
                columns=1, labels_per_sheet=1, dpi=203, scale_percent=100,
                default_copies=1, font_scale_percent=100, offset_x_mm=0, offset_y_mm=0,
                rotation=0, orientation="portrait", show_logo=True, show_printed_at=True,
                active=True, is_default=True,
            )
            self.db.add(template)
        self.db.flush()
        if self.db.query(LabelPrinterTemplate.id).filter(
            LabelPrinterTemplate.tenant_id == self.tenant_id,
            LabelPrinterTemplate.printer_id == printer_id,
            LabelPrinterTemplate.template_id == template_id,
        ).first() is None:
            self.db.add(LabelPrinterTemplate(
                id=f"label-link-{digest}", tenant_id=self.tenant_id,
                printer_id=printer_id, template_id=template_id,
            ))
        self.db.add(LabelSetting(
            tenant_id=self.tenant_id, include_drinks=False, require_reprint_reason=True,
            confirmation_required=True, batch_printing=False,
            default_printer_id=printer_id, default_template_id=template_id,
        ))
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()

    def _resolve_template(self, template_id, printer):
        query = self.db.query(LabelTemplate).filter(LabelTemplate.tenant_id == self.tenant_id, LabelTemplate.active.is_(True))
        if template_id:
            row = query.filter(LabelTemplate.id == template_id).first()
            if row is None:
                raise DomainError("Modelo nao encontrado ou inativo.", code="LabelTemplateNotFound")
            if printer and self.db.query(LabelPrinterTemplate.id).filter(
                LabelPrinterTemplate.tenant_id == self.tenant_id,
                LabelPrinterTemplate.printer_id == printer.id,
                LabelPrinterTemplate.template_id == row.id,
            ).first() is None:
                links = self.db.query(LabelPrinterTemplate.id).filter(
                    LabelPrinterTemplate.tenant_id == self.tenant_id,
                    LabelPrinterTemplate.template_id == row.id,
                ).first()
                if links:
                    raise DomainError("Modelo nao e compativel com a impressora selecionada.", code="LabelPrinterTemplateMismatch")
            return row
        row = query.order_by(LabelTemplate.is_default.desc(), LabelTemplate.name).first()
        if row is None:
            raise DomainError("Configure um modelo de etiqueta antes de gerar a pre-visualizacao.", code="LabelTemplateNotConfigured")
        return row

    def _products(self, order):
        ids = {item.product_id for item in order.items}
        return {row.id: row for row in self.db.query(Product).filter(
            Product.tenant_id == self.tenant_id, Product.id.in_(ids)
        ).all()} if ids else {}

    def _snapshot(self, order, products, *, include_drinks, identity):
        rules = self.db.query(LabelVolumeRule).filter(
            LabelVolumeRule.tenant_id == self.tenant_id, LabelVolumeRule.active.is_(True)
        ).all()
        product_rules = {r.scope_value: r.volumes_per_unit for r in rules if r.scope_type == "product"}
        category_rules = {r.scope_value.strip().casefold(): r.volumes_per_unit for r in rules if r.scope_type == "category"}
        items, volumes, sequence = [], [], 0
        ordered_items = sorted(order.items, key=lambda row: (int(row.position or 0), row.id))
        for item_position, item in enumerate(ordered_items):
            product = products.get(item.product_id)
            is_drink = bool(product and product.product_type == "drink")
            per_unit = product_rules.get(item.product_id)
            if per_unit is None and product and product.category:
                per_unit = category_rules.get(product.category.strip().casefold())
            if per_unit is None:
                per_unit = 0 if is_drink and not include_drinks else 1
            content = {
                "product_id": item.product_id,
                "product_name": product.name if product else (item.flavors[0].flavor_name if item.flavors else "Item"),
                "product_description": product.description if product else None,
                "quantity": int(item.quantity or 0), "selected_size": item.selected_size,
                "selected_crust_type": item.selected_crust_type,
                "selected_drink_variant": item.selected_drink_variant,
                "notes": item.notes, "add_ons": list(item.add_ons or []),
                "flavors": [f.flavor_name for f in sorted(item.flavors, key=lambda x: x.position or 0)],
            }
            items.append({"position": item_position, "order_item_id": item.id, "volumes_per_unit": per_unit, **content})
            for unit_index in range(1, int(item.quantity or 0) + 1):
                for volume_index in range(1, per_unit + 1):
                    sequence += 1
                    volumes.append({"order_item_id": item.id, "sequence": sequence,
                                    "unit_index": unit_index, "volume_index": volume_index, "content": content})
        snapshot = {"order_id": order.id, "order_code": order.order_code, "customer_name": order.delivery_name,
                    "notes": order.notes, "restaurant": identity, "items": items}
        return snapshot, volumes

    def _printer(self, row):
        return {key: getattr(row, key) for key in (
            "id", "name", "description", "system_queue_hint", "printer_type", "connection_type",
            "manufacturer_model", "network_host", "network_port", "protocol", "max_width_mm", "sector",
            "dpi", "active", "is_default", "created_at", "updated_at")}

    def _template(self, row):
        printer_ids = [value for (value,) in self.db.query(LabelPrinterTemplate.printer_id).filter(
            LabelPrinterTemplate.tenant_id == self.tenant_id, LabelPrinterTemplate.template_id == row.id
        ).all()]
        return {**{key: getattr(row, key) for key in (
            "id", "name", "label_type", "width_mm", "height_mm", "margin_top_mm", "margin_right_mm",
            "margin_bottom_mm", "margin_left_mm", "safe_area_mm", "gap_mm", "columns", "labels_per_sheet",
            "dpi", "scale_percent", "default_copies", "font_scale_percent", "offset_x_mm", "offset_y_mm",
            "rotation", "density", "speed", "orientation", "show_logo", "show_printed_at", "active",
            "is_default", "created_at", "updated_at")}, "printer_ids": printer_ids}

    @staticmethod
    def _settings(row):
        if row is None:
            return {"include_drinks": False, "require_reprint_reason": True, "confirmation_required": True,
                    "batch_printing": False, "default_printer_id": None, "default_template_id": None, "updated_at": None}
        return {key: getattr(row, key) for key in ("include_drinks", "require_reprint_reason", "confirmation_required",
                                                    "batch_printing", "default_printer_id", "default_template_id", "updated_at")}

    @staticmethod
    def _rule(row):
        return {key: getattr(row, key) for key in ("id", "scope_type", "scope_value", "volumes_per_unit", "active", "created_at", "updated_at")}

    @staticmethod
    def _job(row):
        return {key: getattr(row, key) for key in ("id", "order_id", "label_version_id", "printer_id", "template_id", "actor_id", "job_type", "copies", "reason", "result_status", "created_at")}
