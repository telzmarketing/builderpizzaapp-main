from __future__ import annotations

import hashlib
import uuid
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from backend.core.exceptions import DomainError
from backend.models.inventory import InventoryItem, InventoryUnit
from backend.models.inventory_portion import InventoryPortionConfig
from backend.schemas.inventory_portion import InventoryPortionConfigIn
from backend.services.idempotency_service import IdempotencyService


class PortionConfigNotFound(DomainError):
    http_status = 404

    def __init__(self):
        super().__init__("Configuracao de porcionamento nao encontrada.", code="PortionConfigNotFound")


class PortionConfigInvalid(DomainError):
    http_status = 400

    def __init__(self, message: str):
        super().__init__(message, code="PortionConfigInvalid")


class PortionConfigConflict(DomainError):
    http_status = 409

    def __init__(self, message: str):
        super().__init__(message, code="PortionConfigConflict")


class InventoryPortionConfigService:
    OPERATION_CREATE = "inventory.portion_config.create"
    OPERATION_UPDATE = "inventory.portion_config.update"
    OPERATION_DEACTIVATE = "inventory.portion_config.deactivate"

    def __init__(self, db: Session, tenant_id: str, actor_id: str):
        self.db = db
        self.tenant_id = tenant_id
        self.actor_id = actor_id

    def list(self, *, active: bool | None = None) -> list[InventoryPortionConfig]:
        query = self.db.query(InventoryPortionConfig).options(
            joinedload(InventoryPortionConfig.source_item),
            joinedload(InventoryPortionConfig.output_item),
            joinedload(InventoryPortionConfig.unit),
        ).filter(InventoryPortionConfig.tenant_id == self.tenant_id)
        if active is not None:
            query = query.filter(InventoryPortionConfig.active.is_(active))
        return query.order_by(InventoryPortionConfig.created_at, InventoryPortionConfig.id).all()

    def get(self, config_id: str) -> InventoryPortionConfig:
        row = self._get(config_id)
        return row

    def create(self, body: InventoryPortionConfigIn, key: str) -> InventoryPortionConfig:
        payload = body.model_dump(mode="json")
        idem = IdempotencyService(self.db, self.tenant_id)
        claim = idem.claim(key, self.OPERATION_CREATE, payload)
        if claim.replay_resource_id:
            return self._get(claim.replay_resource_id)
        try:
            source = self._source(body.source_item_id)
            unit = self._unit(body.unit_id)
            self._validate_source(source)
            self._ensure_not_duplicate(body)

            config_id = str(uuid.uuid4())
            output = InventoryItem(
                id=str(uuid.uuid4()),
                tenant_id=self.tenant_id,
                name=self._output_name(source.name, body, unit.symbol),
                sku=self._output_sku(config_id),
                item_type="finished_good",
                portionable=False,
                category_id=source.category_id,
                unit_id=body.unit_id,
                default_location_id=source.default_location_id,
                min_stock=body.min_stock,
                notes=f"Produto porcionado da materia-prima {source.id}.",
                active=body.active,
            )
            row = InventoryPortionConfig(id=config_id, tenant_id=self.tenant_id, output_item_id=output.id, **payload)
            self.db.add_all([output, row])
            self.db.flush()
            idem.complete(claim.record, row.id)
            self.db.refresh(row)
            return row
        except DomainError:
            idem.abandon(claim.record)
            raise
        except IntegrityError as exc:
            idem.abandon(claim.record)
            raise PortionConfigConflict("Configuracao de porcionamento equivalente ja existe.") from exc
        except Exception:
            idem.abandon(claim.record)
            raise

    def update(self, config_id: str, body: InventoryPortionConfigIn, key: str) -> InventoryPortionConfig:
        payload = body.model_dump(mode="json")
        idem = IdempotencyService(self.db, self.tenant_id)
        claim = idem.claim(key, self.OPERATION_UPDATE, {"config_id": config_id, **payload})
        if claim.replay_resource_id:
            return self._get(claim.replay_resource_id)
        try:
            row = self._get(config_id)
            if body.source_item_id != row.source_item_id:
                raise PortionConfigInvalid("A materia-prima da configuracao nao pode ser trocada; crie uma nova configuracao.")
            self._unit(body.unit_id)
            self._ensure_not_duplicate(body, exclude_id=row.id)
            for field, value in payload.items():
                setattr(row, field, value)
            row.version += 1
            self.db.flush()
            idem.complete(claim.record, row.id)
            self.db.refresh(row)
            return row
        except DomainError:
            idem.abandon(claim.record)
            raise
        except IntegrityError as exc:
            idem.abandon(claim.record)
            raise PortionConfigConflict("Configuracao de porcionamento equivalente ja existe.") from exc
        except Exception:
            idem.abandon(claim.record)
            raise

    def deactivate(self, config_id: str, key: str) -> InventoryPortionConfig:
        idem = IdempotencyService(self.db, self.tenant_id)
        claim = idem.claim(key, self.OPERATION_DEACTIVATE, {"config_id": config_id})
        if claim.replay_resource_id:
            return self._get(claim.replay_resource_id)
        try:
            row = self._get(config_id)
            row.active = False
            row.version += 1
            self.db.flush()
            idem.complete(claim.record, row.id)
            self.db.refresh(row)
            return row
        except DomainError:
            idem.abandon(claim.record)
            raise
        except Exception:
            idem.abandon(claim.record)
            raise

    def _get(self, config_id: str) -> InventoryPortionConfig:
        row = self.db.query(InventoryPortionConfig).options(
            joinedload(InventoryPortionConfig.source_item),
            joinedload(InventoryPortionConfig.output_item),
            joinedload(InventoryPortionConfig.unit),
        ).filter(
            InventoryPortionConfig.id == config_id,
            InventoryPortionConfig.tenant_id == self.tenant_id,
        ).first()
        if row is None:
            raise PortionConfigNotFound()
        return row

    def _source(self, item_id: str) -> InventoryItem:
        row = self.db.query(InventoryItem).filter(InventoryItem.id == item_id, InventoryItem.tenant_id == self.tenant_id).first()
        if row is None:
            raise PortionConfigInvalid("Materia-prima nao encontrada neste tenant.")
        return row

    def _unit(self, unit_id: str) -> InventoryUnit:
        row = self.db.query(InventoryUnit).filter(InventoryUnit.id == unit_id, InventoryUnit.tenant_id == self.tenant_id).first()
        if row is None:
            raise PortionConfigInvalid("Unidade nao encontrada neste tenant.")
        if not row.active:
            raise PortionConfigInvalid("A unidade selecionada esta inativa.")
        return row

    @staticmethod
    def _validate_source(source: InventoryItem) -> None:
        if source.item_type == "finished_good":
            raise PortionConfigInvalid("A materia-prima nao pode ser um produto porcionado.")
        if not source.active:
            raise PortionConfigInvalid("A materia-prima selecionada esta inativa.")

    def _ensure_not_duplicate(self, body: InventoryPortionConfigIn, exclude_id: str | None = None) -> None:
        query = self.db.query(InventoryPortionConfig).filter(
            InventoryPortionConfig.tenant_id == self.tenant_id,
            InventoryPortionConfig.source_item_id == body.source_item_id,
            InventoryPortionConfig.usage == body.usage,
            InventoryPortionConfig.portion_weight == body.portion_weight,
            InventoryPortionConfig.unit_id == body.unit_id,
            InventoryPortionConfig.reference_fraction == body.reference_fraction,
        )
        if body.size is None:
            query = query.filter(InventoryPortionConfig.size.is_(None))
        else:
            query = query.filter(InventoryPortionConfig.size == body.size)
        if exclude_id:
            query = query.filter(InventoryPortionConfig.id != exclude_id)
        if query.first() is not None:
            raise PortionConfigConflict("Configuracao de porcionamento equivalente ja existe.")

    @staticmethod
    def _output_name(source_name: str, body: InventoryPortionConfigIn, symbol: str) -> str:
        suffix = f"{body.portion_weight.normalize()} {symbol}"
        if body.size:
            suffix += f" - {body.size}"
        return f"{source_name} - porcao {suffix}"[:180]

    def _output_sku(self, config_id: str) -> str:
        return "POR-" + hashlib.sha256(f"{self.tenant_id}:{config_id}".encode()).hexdigest()[:20].upper()
