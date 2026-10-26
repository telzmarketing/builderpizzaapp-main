"""Fail-closed contracts shared by marketplace adapters and ingestion."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping


class _NormalizedStrEnum(str, Enum):
    @classmethod
    def normalize(cls, value: str | Enum) -> "_NormalizedStrEnum":
        if isinstance(value, cls):
            return value
        if not isinstance(value, str):
            raise ValueError(f"{cls.__name__} must be a string")

        normalized = value.strip().lower()
        if not normalized:
            raise ValueError(f"{cls.__name__} cannot be empty")
        try:
            return cls(normalized)
        except ValueError as exc:
            raise ValueError(
                f"Unsupported {cls.__name__}: {value!r}"
            ) from exc


class MarketplaceProvider(_NormalizedStrEnum):
    IFOOD = "ifood"
    KEETA = "keeta"
    FOOD99 = "99food"


class MarketplaceOrderOrigin(_NormalizedStrEnum):
    OWN_STORE = "own_store"
    MARKETPLACE = "marketplace"


class MarketplaceEventChannel(_NormalizedStrEnum):
    WEBHOOK = "webhook"
    POLLING = "polling"


class MarketplaceEventState(_NormalizedStrEnum):
    RECEIVED = "received"
    PROCESSING = "processing"
    PROCESSED = "processed"
    DUPLICATE = "duplicate"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"
    QUARANTINED = "quarantined"


class MarketplaceExternalPaymentState(_NormalizedStrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    QUARANTINED = "quarantined"


def _required_id(value: str, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} is required")
    return normalized


def _optional_text(value: str | None, name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    normalized = value.strip()
    return normalized or None


_FORBIDDEN_PAYLOAD_KEYS = frozenset(
    {
        "customer_id",
        "customer",
        "name",
        "full_name",
        "email",
        "phone",
        "mobile",
        "document",
        "cpf",
        "address",
        "street",
        "number",
        "complement",
        "neighborhood",
        "postal_code",
        "zipcode",
    }
)


def _validate_payload(value: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("payload must be a mapping")

    def walk(current: Any, path: str) -> Any:
        if isinstance(current, Mapping):
            sanitized: dict[str, Any] = {}
            for key, item in current.items():
                if not isinstance(key, str):
                    raise ValueError(f"payload key at {path or '<root>'} must be a string")
                key_normalized = key.strip().lower()
                if key_normalized in _FORBIDDEN_PAYLOAD_KEYS:
                    raise ValueError(f"PII/customer field is not allowed: {path + '.' if path else ''}{key}")
                sanitized[key] = walk(item, f"{path}.{key}" if path else key)
            return MappingProxyType(sanitized)
        if isinstance(current, (list, tuple)):
            return tuple(walk(item, f"{path}[]") for item in current)
        return current

    return walk(value, "")


@dataclass(frozen=True, slots=True)
class MarketplaceTenantBinding:
    tenant_id: str
    integration_id: str
    provider: MarketplaceProvider
    external_merchant_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "tenant_id", _required_id(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "integration_id", _required_id(self.integration_id, "integration_id"))
        object.__setattr__(
            self,
            "provider",
            MarketplaceProvider.normalize(self.provider),
        )
        object.__setattr__(
            self,
            "external_merchant_id",
            _required_id(self.external_merchant_id, "external_merchant_id"),
        )


@dataclass(frozen=True, slots=True)
class MarketplaceEventEnvelope:
    event_id: str
    order_id: str | None = None
    event_type: str = ""
    tenant: MarketplaceTenantBinding | None = None
    channel: MarketplaceEventChannel = MarketplaceEventChannel.WEBHOOK
    state: MarketplaceEventState = MarketplaceEventState.RECEIVED
    origin: MarketplaceOrderOrigin = MarketplaceOrderOrigin.MARKETPLACE
    payload: Mapping[str, Any] = field(default_factory=dict)
    correlation_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_id", _required_id(self.event_id, "event_id"))
        if self.order_id is not None:
            object.__setattr__(self, "order_id", _required_id(self.order_id, "order_id"))
        object.__setattr__(self, "event_type", _required_id(self.event_type, "event_type"))
        if not isinstance(self.tenant, MarketplaceTenantBinding):
            raise ValueError("tenant must be MarketplaceTenantBinding")
        object.__setattr__(self, "channel", MarketplaceEventChannel.normalize(self.channel))
        object.__setattr__(self, "state", MarketplaceEventState.normalize(self.state))
        normalized_origin = MarketplaceOrderOrigin.normalize(self.origin)
        if normalized_origin is not MarketplaceOrderOrigin.MARKETPLACE:
            raise ValueError("MarketplaceEventEnvelope origin must be marketplace")
        object.__setattr__(self, "origin", normalized_origin)
        object.__setattr__(self, "payload", _validate_payload(self.payload))
        if self.correlation_id is not None:
            object.__setattr__(
                self,
                "correlation_id",
                _required_id(self.correlation_id, "correlation_id"),
            )


@dataclass(frozen=True, slots=True)
class MarketplaceDeliverySnapshot:
    """Allowlisted operational delivery data kept outside the technical envelope."""

    recipient_name: str | None = None
    phone: str | None = None
    address_line: str | None = None
    address_number: str | None = None
    complement: str | None = None
    neighborhood: str | None = None
    postal_code: str | None = None
    city: str | None = None
    state: str | None = None
    reference: str | None = None
    delivery_instructions: str | None = None

    def __post_init__(self) -> None:
        for field_name in self.__dataclass_fields__:
            object.__setattr__(
                self,
                field_name,
                _optional_text(getattr(self, field_name), field_name),
            )


@dataclass(frozen=True, slots=True)
class MarketplaceExternalPayment:
    """Internal payment status for an already external marketplace payment."""

    state: MarketplaceExternalPaymentState = MarketplaceExternalPaymentState.PENDING
    external_reference: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "state", MarketplaceExternalPaymentState.normalize(self.state))
        if self.external_reference is not None:
            object.__setattr__(
                self,
                "external_reference",
                _required_id(self.external_reference, "external_reference"),
            )
