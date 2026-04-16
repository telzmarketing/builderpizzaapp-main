"""
Centralized state machine for all status transitions.

RULE: no service may set a status directly — it must call
      StateMachine.transition() which validates the move first.

This is the single source of truth for every allowed status
change across the system (loja + ERP share the same rules).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable
from backend.core.exceptions import InvalidStatusTransition


# ── Transition graph ──────────────────────────────────────────────────────────

# Maps current_status → list of allowed next statuses.
# The ORDER of the list is the natural happy-path flow.

ORDER_TRANSITIONS: dict[str, list[str]] = {
    # ── Happy path ──────────────────────────────────────────────────────────────
    # pending → waiting_payment → paid → preparing → on_the_way → delivered
    #
    # REGRA: não pode ir para "preparing" sem pagamento aprovado.
    #        não pode ir para "delivered" sem passar por "on_the_way".
    #        "ready_for_pickup" é intermediário opcional entre preparing e on_the_way.
    # ────────────────────────────────────────────────────────────────────────────
    "pending":           ["waiting_payment", "cancelled"],
    "waiting_payment":   ["paid", "cancelled"],
    "paid":              ["preparing", "cancelled", "refunded"],
    "preparing":         ["ready_for_pickup", "on_the_way", "cancelled"],
    "ready_for_pickup":  ["on_the_way"],
    "on_the_way":        ["delivered"],
    "delivered":         [],          # terminal
    "cancelled":         [],          # terminal
    "refunded":          [],          # terminal
}

DELIVERY_TRANSITIONS: dict[str, list[str]] = {
    "pending_assignment": ["assigned", "cancelled"],
    "assigned":           ["picked_up", "cancelled"],
    "picked_up":          ["on_the_way"],
    "on_the_way":         ["delivered", "failed"],
    "delivered":          ["completed"],
    "completed":          [],         # terminal
    "failed":             ["pending_assignment"],  # can be re-assigned
    "cancelled":          [],         # terminal
}

PAYMENT_TRANSITIONS: dict[str, list[str]] = {
    "pending":   ["paid", "failed"],
    "paid":      ["refunded"],
    "failed":    ["pending"],         # can be retried
    "refunded":  [],
}


# ── Core machine ──────────────────────────────────────────────────────────────

@dataclass
class TransitionResult:
    success: bool
    from_status: str
    to_status: str
    side_effects: list[str] = field(default_factory=list)  # descriptions of what was triggered


class StateMachine:
    """
    Generic state machine.  Instantiate with a transitions graph.

    Usage:
        order_sm   = StateMachine("Order",   ORDER_TRANSITIONS)
        delivery_sm = StateMachine("Delivery", DELIVERY_TRANSITIONS)
        payment_sm  = StateMachine("Payment", PAYMENT_TRANSITIONS)
    """

    def __init__(
        self,
        entity_name: str,
        transitions: dict[str, list[str]],
    ):
        self._name = entity_name
        self._graph = transitions
        self._hooks: dict[str, list[Callable[[str, str], None]]] = {}

    # ── Registration ──────────────────────────────────────────────────────────

    def on_enter(self, status: str, hook: Callable[[str, str], None]) -> None:
        """Register a side-effect that fires whenever `status` is entered.

        hook(entity_id, new_status) is called AFTER the DB commit in the service.
        """
        self._hooks.setdefault(status, []).append(hook)

    # ── Validation ────────────────────────────────────────────────────────────

    def allowed_transitions(self, current_status: str) -> list[str]:
        return self._graph.get(current_status, [])

    def can_transition(self, from_status: str, to_status: str) -> bool:
        return to_status in self._graph.get(from_status, [])

    def assert_transition(self, from_status: str, to_status: str) -> None:
        """Raise InvalidStatusTransition if the move is not allowed."""
        if not self.can_transition(from_status, to_status):
            raise InvalidStatusTransition(
                entity=self._name,
                from_status=from_status,
                to_status=to_status,
                allowed=self.allowed_transitions(from_status),
            )

    # ── Execution ─────────────────────────────────────────────────────────────

    def transition(
        self,
        entity_id: str,
        from_status: str,
        to_status: str,
        *,
        dry_run: bool = False,
    ) -> TransitionResult:
        """
        Validate and execute a status transition.

        :param entity_id:   ID of the order/delivery/payment being changed.
        :param from_status: Current status (read from DB before calling).
        :param to_status:   Desired next status.
        :param dry_run:     If True, only validate — do not fire hooks.
        :returns:           TransitionResult with side-effect descriptions.
        :raises:            InvalidStatusTransition on invalid move.
        """
        self.assert_transition(from_status, to_status)

        result = TransitionResult(
            success=True,
            from_status=from_status,
            to_status=to_status,
        )

        if not dry_run:
            for hook in self._hooks.get(to_status, []):
                try:
                    hook(entity_id, to_status)
                    result.side_effects.append(
                        f"hook:{hook.__name__} fired on enter '{to_status}'"
                    )
                except Exception as exc:
                    # Hooks must never break the main flow — log and continue
                    result.side_effects.append(
                        f"hook:{hook.__name__} ERROR: {exc}"
                    )

        return result

    # ── Introspection ─────────────────────────────────────────────────────────

    def is_terminal(self, status: str) -> bool:
        return self._graph.get(status) == []

    def describe(self) -> dict:
        return {
            "entity": self._name,
            "transitions": self._graph,
            "terminal_states": [s for s, nexts in self._graph.items() if nexts == []],
        }


# ── Singleton instances (shared across the whole app) ─────────────────────────

order_sm    = StateMachine("Order",    ORDER_TRANSITIONS)
delivery_sm = StateMachine("Delivery", DELIVERY_TRANSITIONS)
payment_sm  = StateMachine("Payment",  PAYMENT_TRANSITIONS)
