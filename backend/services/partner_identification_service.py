"""Tenant-safe partner identity configuration and order-origin resolution."""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.core.tenant_context import TenantContext
from backend.models.partner_identification import PartnerIdentificationConfig
from backend.schemas.partner_identification import (
    PartnerIdentificationIn,
    ResolvedOrderIdentificationOut,
)
from backend.services.site_config_service import SiteConfigService


PARTNER_DEFAULTS: dict[str, str] = {
    "own": "Gran Torino",
    "partner_99": "99",
    "ifood": "iFood",
    "keeta": "Keeta",
}
PARTNER_CODES = tuple(PARTNER_DEFAULTS)


class PartnerIdentificationConflict(DomainError):
    http_status = 409


class PartnerIdentificationNotFound(DomainError):
    http_status = 404


class PartnerIdentificationService:
    def __init__(self, db: Session, context: TenantContext | None):
        self.db = db
        self.context = context

    @property
    def tenant_id(self) -> str:
        if self.context is None or not self.context.tenant_id:
            return "tenant-legacy-default"
        return self.context.tenant_id

    @staticmethod
    def _validate_code(partner_code: str) -> str:
        code = (partner_code or "").strip().lower()
        aliases = {"99": "partner_99", "99food": "partner_99"}
        code = aliases.get(code, code)
        if code not in PARTNER_CODES:
            raise DomainError("Origem de parceiro invalida.", code="InvalidPartnerCode")
        return code

    def _row(self, partner_code: str) -> PartnerIdentificationConfig | None:
        code = self._validate_code(partner_code)
        return self.db.query(PartnerIdentificationConfig).filter(
            PartnerIdentificationConfig.tenant_id == self.tenant_id,
            PartnerIdentificationConfig.partner_code == code,
        ).first()

    def _default_name(self, tenant_id: str, code: str) -> str:
        if code == "own":
            try:
                name = SiteConfigService(self.db).operational_identity(tenant_id).get("name")
                if isinstance(name, str) and name.strip():
                    return name.strip()
            except Exception:
                pass
        return PARTNER_DEFAULTS[code]

    @staticmethod
    def serialize(row: PartnerIdentificationConfig) -> dict:
        return {
            "id": row.id,
            "tenant_id": row.tenant_id,
            "partner_code": row.partner_code,
            "display_name": row.display_name,
            "logo_url": row.logo_url,
            "active": bool(row.active),
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    def list(self) -> list[dict]:
        rows = self.db.query(PartnerIdentificationConfig).filter(
            PartnerIdentificationConfig.tenant_id == self.tenant_id,
        ).all()
        by_code = {row.partner_code: row for row in rows}
        result = []
        for code in PARTNER_CODES:
            row = by_code.get(code)
            if row is not None:
                result.append(self.serialize(row))
            else:
                result.append({
                    "id": None,
                    "tenant_id": self.tenant_id,
                    "partner_code": code,
                    "display_name": self._default_name(self.tenant_id, code),
                    "logo_url": None,
                    "active": True,
                    "created_at": None,
                    "updated_at": None,
                })
        return result

    def get(self, partner_code: str) -> dict:
        code = self._validate_code(partner_code)
        row = self._row(code)
        if row is not None:
            return self.serialize(row)
        return {
            "id": None,
            "tenant_id": self.tenant_id,
            "partner_code": code,
            "display_name": self._default_name(self.tenant_id, code),
            "logo_url": None,
            "active": True,
            "created_at": None,
            "updated_at": None,
        }

    def create(self, payload: PartnerIdentificationIn) -> dict:
        code = self._validate_code(payload.partner_code)
        if self._row(code) is not None:
            raise PartnerIdentificationConflict(
                "A identificacao deste parceiro ja existe.",
                code="PartnerIdentificationAlreadyExists",
            )
        row = PartnerIdentificationConfig(
            id=str(uuid.uuid4()), tenant_id=self.tenant_id, partner_code=code,
            display_name=payload.display_name, logo_url=payload.logo_url, active=payload.active,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return self.serialize(row)

    def update(self, partner_code: str, payload: PartnerIdentificationIn) -> dict:
        code = self._validate_code(partner_code)
        if payload.partner_code != code:
            raise DomainError("O codigo do parceiro da URL e do corpo deve ser igual.", code="PartnerCodeMismatch")
        row = self._row(code)
        if row is None:
            return self.create(payload)
        row.display_name = payload.display_name
        row.logo_url = payload.logo_url
        row.active = payload.active
        self.db.commit()
        self.db.refresh(row)
        return self.serialize(row)

    def delete(self, partner_code: str) -> None:
        row = self._row(partner_code)
        if row is None:
            raise PartnerIdentificationNotFound(
                "Identificacao configurada nao encontrada.", code="PartnerIdentificationNotFound",
            )
        self.db.delete(row)
        self.db.commit()

    def resolved_for_orders(self, orders) -> dict[str, dict]:
        tenant_ids = {getattr(order, "tenant_id", None) for order in orders if getattr(order, "tenant_id", None)}
        if not tenant_ids:
            tenant_ids = {self.tenant_id}
        try:
            rows = self.db.query(PartnerIdentificationConfig).filter(
                PartnerIdentificationConfig.tenant_id.in_(tenant_ids),
            ).all()
        except Exception:
            # Keep legacy SQLite fixtures and pre-migration runtimes operational;
            # the persisted configuration is used as soon as its migration exists.
            self.db.rollback()
            rows = []
        by_key = {(row.tenant_id, row.partner_code): row for row in rows}
        resolved: dict[str, dict] = {}
        for order in orders:
            code = self._validate_code(getattr(order, "order_origin", None) or "own")
            row = by_key.get((getattr(order, "tenant_id", None), code))
            resolved[order.id] = {
                "code": code,
                "display_name": row.display_name if row else self._default_name(getattr(order, "tenant_id", None) or self.tenant_id, code),
                "logo_url": row.logo_url if row else None,
                "partner_order_number": getattr(order, "partner_order_number", None),
            }
        return resolved
