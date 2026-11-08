from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from backend.core.exceptions import DomainError
from backend.models.inventory import InventoryItem, InventoryUnit
from backend.models.inventory import InventoryStockMovement
from backend.models.inventory_foundation import InventoryReservation, InventoryLot
from backend.models.preparation import InventoryOperationRecipe, PreparationOrder
from backend.models.inventory_portion import InventoryPortionConfig
from backend.schemas.inventory_portion import InventoryPortionConfigIn
from backend.services.idempotency_service import IdempotencyService


def display_portion_name(row: InventoryPortionConfig) -> str:
    """Build a stable human-readable portion name without Decimal exponent notation."""
    weight = format(row.portion_weight, "f").rstrip("0").rstrip(".") or "0"
    symbol = row.unit.symbol if row.unit else ""
    source_name = row.source_item.name if row.source_item else (row.output_item.name if row.output_item else "Porcao")
    return f"{source_name} - porcao {weight} {symbol}" + (f" - {row.size}" if row.size else "")


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

    def balances(self) -> list[dict]:
        configs = self.list(active=True)
        if not configs:
            return []
        output_ids = [row.output_item_id for row in configs]
        physical_rows = self.db.query(
            InventoryStockMovement.item_id,
            func.coalesce(func.sum(InventoryStockMovement.quantity_delta), 0),
        ).filter(
            InventoryStockMovement.tenant_id == self.tenant_id,
            InventoryStockMovement.item_id.in_(output_ids),
        ).group_by(InventoryStockMovement.item_id).all()
        reserved_rows = self.db.query(
            InventoryReservation.item_id,
            func.coalesce(func.sum(InventoryReservation.quantity), 0),
        ).filter(
            InventoryReservation.tenant_id == self.tenant_id,
            InventoryReservation.item_id.in_(output_ids),
            InventoryReservation.status == "active",
            or_(
                InventoryReservation.expires_at.is_(None),
                InventoryReservation.expires_at > datetime.now(timezone.utc),
            ),
        ).group_by(InventoryReservation.item_id).all()
        preparing_rows = self.db.query(
            InventoryOperationRecipe.output_item_id,
            func.coalesce(func.sum(PreparationOrder.target_quantity - PreparationOrder.produced_quantity - PreparationOrder.lost_quantity - PreparationOrder.discarded_quantity), 0),
        ).join(
            PreparationOrder,
            PreparationOrder.recipe_id == InventoryOperationRecipe.id,
        ).filter(
            InventoryOperationRecipe.tenant_id == self.tenant_id,
            PreparationOrder.tenant_id == self.tenant_id,
            InventoryOperationRecipe.output_item_id.in_(output_ids),
            PreparationOrder.status.in_(("approved", "scheduled", "waiting", "in_progress", "paused", "partially_completed")),
        ).group_by(InventoryOperationRecipe.output_item_id).all()
        physical = {item_id: value for item_id, value in physical_rows}
        cost_rows = self.db.query(
            InventoryStockMovement.item_id,
            func.coalesce(func.sum(InventoryStockMovement.quantity_delta * InventoryStockMovement.unit_cost), 0),
        ).filter(
            InventoryStockMovement.tenant_id == self.tenant_id,
            InventoryStockMovement.item_id.in_(output_ids),
            InventoryStockMovement.quantity_delta > 0,
            InventoryStockMovement.unit_cost > 0,
        ).group_by(InventoryStockMovement.item_id).all()
        costs = {item_id: value for item_id, value in cost_rows}
        expiry_rows = self.db.query(InventoryLot.item_id, func.min(InventoryLot.expires_on)).filter(
            InventoryLot.tenant_id == self.tenant_id,
            InventoryLot.item_id.in_(output_ids),
            InventoryLot.status == "available",
            InventoryLot.expires_on.is_not(None),
        ).group_by(InventoryLot.item_id).all()
        expiries = {item_id: value for item_id, value in expiry_rows}
        reserved = {item_id: value for item_id, value in reserved_rows}
        preparing = {item_id: value for item_id, value in preparing_rows}
        return [{
            "config_id": row.id,
            "output_item_id": row.output_item_id,
            "output_item_name": display_portion_name(row),
            "source_item_name": row.source_item.name if row.source_item else None,
            "unit_symbol": row.unit.symbol if row.unit else None,
            "usage": row.usage,
            "physical_stock": physical.get(row.output_item_id, 0),
            "reserved_stock": reserved.get(row.output_item_id, 0),
            "available_stock": max(0, physical.get(row.output_item_id, 0) - reserved.get(row.output_item_id, 0)),
            "in_preparation": max(0, preparing.get(row.output_item_id, 0)),
            "min_stock": row.min_stock,
            "target_stock": row.target_stock,
            "active": row.active,
            "unit_cost": (Decimal(str(costs.get(row.output_item_id, 0))) / Decimal(str(physical.get(row.output_item_id, 0)))).quantize(Decimal("0.00000001")) if Decimal(str(physical.get(row.output_item_id, 0))) > 0 else Decimal("0"),
            "next_expiry": expiries.get(row.output_item_id),
        } for row in configs]

    def replenishment_alerts(self) -> list[dict]:
        balances = {row["config_id"]: row for row in self.balances()}
        alerts = []
        for row in self.list(active=True):
            balance = balances[row.id]
            available = Decimal(str(balance["available_stock"] or 0))
            in_preparation = Decimal(str(balance["in_preparation"] or 0))
            minimum = Decimal(str(row.min_stock or 0))
            target = Decimal(str(row.target_stock or 0))
            suggested = max(Decimal("0"), target - available - in_preparation)
            # The configured portion weight is expressed in the source unit.
            # Yield is a percentage of usable source material after technical loss.
            source_quantity = (suggested * Decimal(str(row.portion_weight)) * Decimal("100") / Decimal(str(row.yield_percent))).quantize(Decimal("0.000001"))
            alerts.append({
                "config_id": row.id,
                "output_item_id": row.output_item_id,
                "output_item_name": display_portion_name(row),
                "source_item_name": row.source_item.name if row.source_item else None,
                "unit_symbol": row.unit.symbol if row.unit else None,
                "usage": row.usage,
                "available_stock": available,
                "in_preparation": in_preparation,
                "min_stock": minimum,
                "target_stock": target,
                "suggested_portions": suggested,
                "estimated_source_quantity": source_quantity,
                "status": "alert" if available + in_preparation <= minimum and suggested > 0 else "ok",
            })
        return alerts

    def create_preparation_order(self, config_id: str, body, key: str):
        row = self._get(config_id)
        if not row.active:
            raise PortionConfigInvalid("A configuracao de porcao esta inativa.")
        if row.usage == "direct":
            raise PortionConfigInvalid("Configuracoes de utilizacao direta nao geram ordem de preparo.")
        recipe = self.db.query(InventoryOperationRecipe).filter(
            InventoryOperationRecipe.tenant_id == self.tenant_id,
            InventoryOperationRecipe.output_item_id == row.output_item_id,
            InventoryOperationRecipe.active.is_(True),
        ).order_by(InventoryOperationRecipe.version_number.desc(), InventoryOperationRecipe.id.desc()).first()
        if recipe is None:
            raise PortionConfigConflict("Cadastre uma ficha operacional ativa para este produto porcionado antes de solicitar o preparo.")
        from backend.schemas.preparation import PreparationOrderIn
        from backend.services.preparation_service import PreparationService
        order_body = PreparationOrderIn(
            recipe_id=recipe.id,
            target_quantity=body.target_quantity,
            scheduled_for=body.scheduled_for,
            notes=body.notes,
            expected_version=body.expected_version,
        )
        return PreparationService(self.db, self.tenant_id, self.actor_id).create_order(order_body, key)

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
            if body.unit_id != row.unit_id:
                raise PortionConfigInvalid("A unidade de uma configuracao existente nao pode ser trocada; desative-a e crie uma nova configuracao para preservar o historico fisico.")
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
        # Selecting an item in this screen is the explicit operational choice
        # that enables portioning for it. Keep the cadastro flag synchronized
        # without requiring a second, blocking step in another screen.
        source.portionable = True

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
        weight = format(body.portion_weight, "f").rstrip("0").rstrip(".") or "0"
        suffix = f"{weight} {symbol}"
        if body.size:
            suffix += f" - {body.size}"
        return f"{source_name} - porcao {suffix}"[:180]

    def _output_sku(self, config_id: str) -> str:
        return "POR-" + hashlib.sha256(f"{self.tenant_id}:{config_id}".encode()).hexdigest()[:20].upper()
