"""
Domain exceptions — all business-rule violations raise one of these.

Design rule: services NEVER raise generic Python exceptions for domain errors.
Routes catch DomainError subclasses and map them to HTTP status codes.
"""


class DomainError(Exception):
    """Base for all business-rule violations."""
    http_status: int = 400

    def __init__(self, message: str, *, code: str | None = None):
        super().__init__(message)
        self.message = message
        self.code = code or self.__class__.__name__

    def to_dict(self) -> dict:
        return {"error": self.code, "detail": self.message}


# ── Order ─────────────────────────────────────────────────────────────────────

class OrderNotFound(DomainError):
    http_status = 404
    def __init__(self, order_id: str):
        super().__init__(f"Pedido '{order_id}' não encontrado.")


class OrderAlreadyPaid(DomainError):
    def __init__(self, order_id: str):
        super().__init__(f"Pedido '{order_id}' já foi pago.")


class OrderCancelled(DomainError):
    def __init__(self, order_id: str):
        super().__init__(f"Pedido '{order_id}' está cancelado e não pode ser alterado.")


class InvalidStatusTransition(DomainError):
    def __init__(self, entity: str, from_status: str, to_status: str, allowed: list[str]):
        allowed_str = ", ".join(allowed) if allowed else "nenhum"
        super().__init__(
            f"{entity}: transição '{from_status}' → '{to_status}' não permitida. "
            f"Próximos estados válidos: [{allowed_str}]."
        )


class CartEmpty(DomainError):
    def __init__(self):
        super().__init__("O carrinho está vazio.")


class ProductNotFound(DomainError):
    http_status = 404
    def __init__(self, product_id: str):
        super().__init__(f"Produto '{product_id}' não encontrado ou inativo.")


class PriceConflict(DomainError):
    def __init__(self, product_name: str, frontend_price: float, server_price: float):
        super().__init__(
            f"Preço inconsistente para '{product_name}': "
            f"recebido R${frontend_price:.2f}, esperado R${server_price:.2f}."
        )


class FlavorDivisionMismatch(DomainError):
    def __init__(self, product_id: str, division: int, provided: int):
        super().__init__(
            f"Item '{product_id}': flavor_division={division} "
            f"mas {provided} sabor(es) enviado(s)."
        )


class MaxFlavorsExceeded(DomainError):
    def __init__(self, division: int, max_allowed: int):
        super().__init__(
            f"Divisão de {division} sabores não permitida. Máximo configurado: {max_allowed}."
        )


# ── Payment ───────────────────────────────────────────────────────────────────

class PaymentNotFound(DomainError):
    http_status = 404
    def __init__(self, order_id: str):
        super().__init__(f"Pagamento para o pedido '{order_id}' não encontrado.")


class PaymentAlreadyExists(DomainError):
    http_status = 409
    def __init__(self, order_id: str):
        super().__init__(f"Pedido '{order_id}' já possui um pagamento registrado.")


class PaymentOrderNotEligible(DomainError):
    """Raised when trying to create a payment for an order that is not in 'pending' status."""
    def __init__(self, order_id: str, current_status: str):
        super().__init__(
            f"Não é possível criar pagamento para o pedido '{order_id}' "
            f"(status atual: '{current_status}'). "
            f"O pedido precisa estar em 'pending'."
        )


class PaymentAmountMismatch(DomainError):
    def __init__(self, expected: float, received: float):
        super().__init__(
            f"Valor inconsistente: pedido exige R${expected:.2f}, recebido R${received:.2f}."
        )


class GatewayError(DomainError):
    def __init__(self, gateway: str, detail: str):
        super().__init__(f"Erro no gateway '{gateway}': {detail}")


class WebhookSignatureInvalid(DomainError):
    http_status = 403
    def __init__(self):
        super().__init__("Assinatura do webhook inválida.")


class GatewayNotConfigured(DomainError):
    def __init__(self, gateway: str, field: str):
        super().__init__(
            f"Gateway '{gateway}' não configurado: campo '{field}' ausente. "
            f"Configure em Admin → Pagamentos."
        )


# ── Shipping ──────────────────────────────────────────────────────────────────

class NoShippingRuleFound(DomainError):
    def __init__(self, city: str):
        super().__init__(
            f"Nenhuma regra de frete encontrada para a cidade '{city}'. "
            f"Cadastre uma regra global em Admin → Frete."
        )


class ShippingZoneNotFound(DomainError):
    http_status = 404
    def __init__(self, zone_id: str):
        super().__init__(f"Zona de frete '{zone_id}' não encontrada.")


class ShippingRuleNotFound(DomainError):
    http_status = 404
    def __init__(self, rule_id: str):
        super().__init__(f"Regra de frete '{rule_id}' não encontrada.")


# ── Coupon ────────────────────────────────────────────────────────────────────

class CouponNotFound(DomainError):
    http_status = 404
    def __init__(self, code: str):
        super().__init__(f"Cupom '{code}' não encontrado ou inativo.")


class CouponExpired(DomainError):
    def __init__(self, code: str):
        super().__init__(f"Cupom '{code}' expirado.")


class CouponExhausted(DomainError):
    def __init__(self, code: str):
        super().__init__(f"Cupom '{code}' esgotado.")


class CouponMinValueNotMet(DomainError):
    def __init__(self, code: str, min_value: float, subtotal: float):
        super().__init__(
            f"Cupom '{code}' requer pedido mínimo de R${min_value:.2f}. "
            f"Seu subtotal: R${subtotal:.2f}."
        )


# ── Delivery ──────────────────────────────────────────────────────────────────

class DeliveryNotFound(DomainError):
    http_status = 404
    def __init__(self, delivery_id: str):
        super().__init__(f"Entrega '{delivery_id}' não encontrada.")


class DeliveryPersonNotFound(DomainError):
    http_status = 404
    def __init__(self, person_id: str):
        super().__init__(f"Motoboy '{person_id}' não encontrado ou inativo.")


class DeliveryPersonUnavailable(DomainError):
    def __init__(self, person_id: str):
        super().__init__(
            f"Motoboy '{person_id}' está ocupado com outra entrega. "
            f"Aguarde a conclusão ou escolha outro."
        )


class OrderNotReadyForDelivery(DomainError):
    def __init__(self, order_id: str, current_status: str):
        super().__init__(
            f"Pedido '{order_id}' não pode receber motoboy "
            f"(status atual: '{current_status}'). "
            f"O pedido precisa estar em 'preparing' ou 'ready_for_pickup'."
        )


class DeliveryAlreadyAssigned(DomainError):
    def __init__(self, order_id: str):
        super().__init__(f"Pedido '{order_id}' já possui entrega atribuída.")
