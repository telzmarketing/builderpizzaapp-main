"""Application service for the tenant-isolated, read-only TV order board."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import secrets
import string
import uuid
from sqlalchemy.orm import Session, contains_eager

from backend.core.exceptions import DomainError
from backend.config import get_settings as get_app_settings
from backend.core.tenant_context import TenantContext
from backend.models.delivery import Delivery, DeliveryPerson, DeliveryStatus
from backend.models.order import Order, OrderStatus
from backend.models.order_board import OrderBoardActivation, OrderBoardDevice, OrderBoardSetting
from backend.models.platform_saas import TenantProfile
from backend.models.tenant import Tenant
from backend.schemas.order_board import OrderBoardSettingsIn


ACTIVE_STATUSES = (
    OrderStatus.preparing,
    OrderStatus.ready_for_pickup,
)
ACTIVATION_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


class OrderBoardUnauthorized(DomainError):
    http_status = 401


class OrderBoardForbidden(DomainError):
    http_status = 403


class OrderBoardNotFound(DomainError):
    http_status = 404


class OrderBoardConflict(DomainError):
    http_status = 409


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class OrderBoardService:
    def __init__(self, db: Session, context: TenantContext | None = None):
        self.db = db
        self.context = context

    @property
    def tenant_id(self) -> str:
        if self.context is None:
            raise RuntimeError("Contexto tenant obrigatorio para operacoes administrativas.")
        return self.context.tenant_id

    def _settings(self, tenant_id: str | None = None) -> OrderBoardSetting:
        resolved = tenant_id or self.tenant_id
        row = self.db.query(OrderBoardSetting).filter(OrderBoardSetting.tenant_id == resolved).first()
        if row is None:
            row = OrderBoardSetting(tenant_id=resolved)
            self.db.add(row)
            self.db.flush()
        return row

    @staticmethod
    def serialize_settings(
        row: OrderBoardSetting, *, company_name: str | None = None,
        logo_url: str | None = None,
    ) -> dict:
        return {
            "company_name": company_name,
            "logo_url": logo_url,
            "enabled": bool(row.enabled),
            "production_sla_minutes": row.production_sla_minutes,
            "dispatch_sla_minutes": row.dispatch_sla_minutes,
            "completed_window_seconds": row.completed_window_seconds,
            "polling_interval_seconds": row.polling_interval_seconds,
            "sound_enabled": bool(row.sound_enabled),
            "max_orders": row.max_orders,
            "updated_at": row.updated_at,
        }

    def _tenant_branding(self, *, create_profile: bool = False) -> tuple[Tenant, TenantProfile | None]:
        tenant = self.db.query(Tenant).filter(
            Tenant.id == self.tenant_id,
            Tenant.deleted_at.is_(None),
        ).first()
        if tenant is None:
            raise OrderBoardNotFound("Estabelecimento nao encontrado.", code="OrderBoardTenantNotFound")
        profile = self.db.query(TenantProfile).filter(TenantProfile.tenant_id == self.tenant_id).first()
        if profile is None and create_profile:
            profile = TenantProfile(tenant_id=self.tenant_id)
            self.db.add(profile)
            self.db.flush()
        return tenant, profile

    @staticmethod
    def serialize_device(row: OrderBoardDevice) -> dict:
        return {
            "id": row.id,
            "name": row.name,
            "status": row.status,
            "activated_at": row.activated_at,
            "last_seen_at": row.last_seen_at,
            "revoked_at": row.revoked_at,
            "created_at": row.created_at,
        }

    def get_settings(self) -> dict:
        row = self._settings()
        tenant, profile = self._tenant_branding()
        self.db.commit()
        self.db.refresh(row)
        return self.serialize_settings(
            row,
            company_name=profile.trade_name if profile and profile.trade_name else tenant.name,
            logo_url=profile.logo_url if profile else None,
        )

    def update_settings(self, body: OrderBoardSettingsIn) -> dict:
        row = self._settings()
        tenant, profile = self._tenant_branding(create_profile=True)
        values = body.model_dump()
        company_name = values.pop("company_name")
        logo_url = values.pop("logo_url")
        for field, value in values.items():
            setattr(row, field, value)
        profile.trade_name = company_name
        profile.logo_url = logo_url
        row.updated_at = _utcnow()
        self.db.commit()
        self.db.refresh(row)
        return self.serialize_settings(
            row,
            company_name=profile.trade_name or tenant.name,
            logo_url=profile.logo_url,
        )

    def list_devices(self) -> list[dict]:
        rows = self.db.query(OrderBoardDevice).filter(
            OrderBoardDevice.tenant_id == self.tenant_id
        ).order_by(OrderBoardDevice.created_at.desc()).all()
        return [self.serialize_device(row) for row in rows]

    def _device_for_admin(self, device_id: str) -> OrderBoardDevice:
        row = self.db.query(OrderBoardDevice).filter(
            OrderBoardDevice.id == device_id,
            OrderBoardDevice.tenant_id == self.tenant_id,
        ).first()
        if row is None:
            raise OrderBoardNotFound("Painel nao encontrado neste estabelecimento.", code="OrderBoardDeviceNotFound")
        return row

    def rename_device(self, device_id: str, name: str) -> dict:
        row = self._device_for_admin(device_id)
        row.name = name.strip()
        row.updated_at = _utcnow()
        self.db.commit()
        self.db.refresh(row)
        return self.serialize_device(row)

    def revoke_device(self, device_id: str) -> dict:
        row = self._device_for_admin(device_id)
        now = _utcnow()
        row.status = "revoked"
        row.revoked_at = row.revoked_at or now
        row.token_hash = None
        row.updated_at = now
        self.db.commit()
        self.db.refresh(row)
        return self.serialize_device(row)

    def delete_device(self, device_id: str) -> dict:
        row = self._device_for_admin(device_id)
        payload = self.serialize_device(row)
        self.db.delete(row)
        self.db.commit()
        return payload

    def create_activation(self) -> dict:
        if not get_app_settings().ORDER_BOARD_ENABLED:
            raise OrderBoardForbidden("Painel de pedidos indisponivel neste ambiente.", code="OrderBoardGloballyDisabled")
        now = _utcnow()
        claim_token = secrets.token_urlsafe(32)
        for _ in range(20):
            code = "".join(secrets.choice(ACTIVATION_ALPHABET) for _ in range(8))
            if self.db.query(OrderBoardActivation.id).filter(
                OrderBoardActivation.code_prefix == code[:4]
            ).first() is None:
                break
        else:
            raise OrderBoardConflict("Nao foi possivel reservar um codigo de ativacao.", code="OrderBoardActivationCapacity")
        salt = secrets.token_hex(8)
        row = OrderBoardActivation(
            id=str(uuid.uuid4()),
            code_prefix=code[:4],
            code_salt=salt,
            code_hash=_digest(f"{salt}:{code}"),
            claim_token_hash=_digest(claim_token),
            status="pending",
            expires_at=now + timedelta(minutes=10),
        )
        self.db.add(row)
        self.db.commit()
        return {
            "id": row.id,
            "code": code,
            "expires_at": row.expires_at,
            "poll_after_seconds": 3,
            "_claim_token": claim_token,
        }

    def approve_activation(self, code: str, name: str, *, actor_id: str) -> dict:
        normalized = "".join(code.upper().split())
        now = _utcnow()
        selected = self.db.query(OrderBoardActivation).filter(
            OrderBoardActivation.status == "pending",
            OrderBoardActivation.code_prefix == normalized[:4],
            OrderBoardActivation.failed_attempts < 5,
        ).with_for_update().first()
        if selected is None:
            raise OrderBoardNotFound("Codigo de ativacao invalido ou expirado.", code="OrderBoardActivationNotFound")
        if _aware(selected.expires_at) <= now:
            selected.status = "expired"
            self.db.commit()
            raise OrderBoardNotFound("Codigo de ativacao invalido ou expirado.", code="OrderBoardActivationNotFound")
        expected = _digest(f"{selected.code_salt}:{normalized}")
        if not secrets.compare_digest(selected.code_hash, expected):
            selected.failed_attempts += 1
            if selected.failed_attempts >= 5:
                selected.status = "cancelled"
            self.db.commit()
            raise OrderBoardNotFound("Codigo de ativacao invalido ou expirado.", code="OrderBoardActivationNotFound")

        self._settings()
        device = OrderBoardDevice(
            id=str(uuid.uuid4()),
            tenant_id=self.tenant_id,
            name=name.strip(),
            status="active",
            activated_at=now,
            created_by=actor_id,
        )
        self.db.add(device)
        self.db.flush()
        selected.status = "approved"
        selected.tenant_id = self.tenant_id
        selected.device_id = device.id
        selected.approved_by = actor_id
        selected.approved_at = now
        self.db.commit()
        self.db.refresh(device)
        return self.serialize_device(device)

    def activation_status(self, activation_id: str, claim_token: str) -> tuple[dict, str | None]:
        row = self.db.query(OrderBoardActivation).filter(
            OrderBoardActivation.id == activation_id
        ).with_for_update().first()
        if row is None or not secrets.compare_digest(row.claim_token_hash, _digest(claim_token)):
            raise OrderBoardUnauthorized("Ativacao nao reconhecida.", code="OrderBoardActivationUnauthorized")
        now = _utcnow()
        if row.status in {"pending", "approved"} and _aware(row.expires_at) <= now:
            row.status = "expired"
            self.db.commit()
        if row.status == "expired":
            return {"status": "expired", "expires_at": row.expires_at, "device": None}, None
        if row.status == "approved":
            device = self.db.query(OrderBoardDevice).filter(
                OrderBoardDevice.id == row.device_id,
                OrderBoardDevice.status == "active",
            ).first()
            if device is None:
                raise OrderBoardConflict("Dispositivo aprovado nao esta mais ativo.", code="OrderBoardDeviceUnavailable")
            secret = secrets.token_urlsafe(32)
            device.token_hash = _digest(secret)
            device.updated_at = now
            row.status = "claimed"
            row.claimed_at = row.claimed_at or now
            self.db.commit()
            return {
                "status": "claimed",
                "expires_at": row.expires_at,
                "device": self.serialize_device(device),
            }, f"{device.id}.{secret}"
        device = self.db.query(OrderBoardDevice).filter(OrderBoardDevice.id == row.device_id).first() if row.device_id else None
        return {
            "status": row.status,
            "expires_at": row.expires_at,
            "device": self.serialize_device(device) if device else None,
        }, None

    def authenticate_device(self, credential: str | None) -> OrderBoardDevice:
        if not credential or "." not in credential:
            raise OrderBoardUnauthorized("Painel nao vinculado.", code="OrderBoardDeviceUnauthorized")
        device_id, secret = credential.split(".", 1)
        device = self.db.query(OrderBoardDevice).filter(
            OrderBoardDevice.id == device_id,
            OrderBoardDevice.status == "active",
        ).first()
        if device is None or not device.token_hash or not secrets.compare_digest(device.token_hash, _digest(secret)):
            raise OrderBoardUnauthorized("Credencial do painel invalida ou revogada.", code="OrderBoardDeviceUnauthorized")
        return device

    def heartbeat(self, device: OrderBoardDevice) -> dict:
        now = _utcnow()
        if device.last_seen_at is None or now - _aware(device.last_seen_at) >= timedelta(seconds=15):
            device.last_seen_at = now
            device.updated_at = now
            self.db.commit()
        return {"device_id": device.id, "last_seen_at": device.last_seen_at}

    def snapshot(self, device: OrderBoardDevice) -> tuple[dict, str]:
        now = _utcnow()
        if not get_app_settings().ORDER_BOARD_ENABLED:
            raise OrderBoardForbidden("Painel de pedidos indisponivel neste ambiente.", code="OrderBoardGloballyDisabled")
        settings = self._settings(device.tenant_id)
        if not settings.enabled:
            self.db.rollback()
            raise OrderBoardForbidden("Painel de pedidos desativado para este estabelecimento.", code="OrderBoardDisabled")
        tenant_row = (
            self.db.query(Tenant, TenantProfile)
            .outerjoin(TenantProfile, TenantProfile.tenant_id == Tenant.id)
            .filter(
                Tenant.id == device.tenant_id,
                Tenant.status == "active",
                Tenant.deleted_at.is_(None),
            )
            .first()
        )
        if tenant_row is None:
            raise OrderBoardForbidden("Estabelecimento indisponivel.", code="OrderBoardTenantUnavailable")
        tenant, profile = tenant_row

        display_rows = (
            self.db.query(Order)
            .join(Order.delivery)
            .join(Delivery.delivery_person)
            .options(
                contains_eager(Order.delivery).contains_eager(Delivery.delivery_person)
            )
            .filter(
                Order.tenant_id == device.tenant_id,
                Order.fulfillment_type == "delivery",
                Order.status.in_(ACTIVE_STATUSES),
                Delivery.tenant_id == device.tenant_id,
                Delivery.delivery_person_id.is_not(None),
                Delivery.status == DeliveryStatus.assigned,
                DeliveryPerson.tenant_id == device.tenant_id,
            )
            .order_by(Order.created_at.asc(), Order.id.asc())
            .limit(settings.max_orders)
            .all()
        )
        serialized = [self._serialize_order(row) for row in display_rows]

        payload = {
            "tenant": {
                "name": profile.trade_name if profile and profile.trade_name else tenant.name,
                "logo_url": profile.logo_url if profile else None,
                "timezone": tenant.timezone,
            },
            "settings": self.serialize_settings(
                settings,
                company_name=profile.trade_name if profile and profile.trade_name else tenant.name,
                logo_url=profile.logo_url if profile else None,
            ),
            "orders": serialized,
            "server_time": now,
        }
        fingerprint_payload = {**payload, "server_time": None}
        etag = '"' + hashlib.sha256(
            json.dumps(fingerprint_payload, default=str, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest() + '"'
        return payload, etag

    @staticmethod
    def _serialize_order(order: Order) -> dict:
        status = order.status.value if hasattr(order.status, "value") else str(order.status)
        return {
            "id": order.id,
            "order_code": order.order_code,
            "status": status,
            "created_at": order.created_at,
            "preparation_started_at": order.preparation_started_at,
            "ready_for_pickup_at": order.ready_for_pickup_at,
            "delivery": {
                "provider_key": "own",
                "provider_label": "Motoboy Próprio",
                "driver_name": order.delivery.delivery_person.name,
            },
        }
