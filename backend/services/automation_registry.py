"""Versioned whitelist for safe, cross-module automations."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class RegistryItem:
    key: str
    module: str
    label: str
    description: str
    required_config: tuple[str, ...] = ()

    def public(self) -> dict[str, Any]:
        value = asdict(self)
        value["required_config"] = list(self.required_config)
        return value


TRIGGERS = {
    item.key: item for item in (
        RegistryItem("customer.created", "crm", "Cliente criado", "Novo cliente persistido."),
        RegistryItem("customer.tag_assigned", "crm", "Tag atribuida", "Tag atribuida a um cliente."),
        RegistryItem("order.created", "orders", "Pedido criado", "Novo pedido persistido."),
        RegistryItem("order.status_changed", "orders", "Status do pedido alterado", "Mudanca de status do pedido."),
        RegistryItem("payment.confirmed", "payments", "Pagamento confirmado", "Pagamento confirmado pelo gateway."),
        RegistryItem("loyalty.level_up", "loyalty", "Nivel de fidelidade alterado", "Cliente subiu de nivel."),
    )
}

CONDITIONS = {
    "eq": "Igual a", "neq": "Diferente de", "in": "Contido em",
    "gt": "Maior que", "gte": "Maior ou igual", "lt": "Menor que",
    "lte": "Menor ou igual", "contains": "Contem", "exists": "Existe",
}

ACTIONS = {
    item.key: item for item in (
        RegistryItem("crm.assign_tag", "crm", "Atribuir tag", "Atribui uma tag existente ao cliente.", ("tag_id",)),
        RegistryItem("crm.create_task", "crm", "Criar tarefa", "Cria tarefa de CRM para acompanhamento.", ("title",)),
        RegistryItem("notification.send_whatsapp", "notifications", "Enviar WhatsApp", "Envia via fluxo existente com consentimento e rating.", ("message",)),
        RegistryItem("notification.send_email", "notifications", "Enviar e-mail", "Envia via fluxo existente com consentimento.", ("subject", "message")),
    )
}


def catalog() -> dict[str, Any]:
    return {
        "version": 1,
        "triggers": [item.public() for item in TRIGGERS.values()],
        "conditions": [{"key": key, "label": label} for key, label in CONDITIONS.items()],
        "actions": [item.public() for item in ACTIONS.values()],
    }


def validate_definition(definition: Any) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    trigger = TRIGGERS.get(definition.trigger.key)
    if not trigger:
        errors.append({"path": "trigger.key", "code": "unsupported_trigger", "message": "Gatilho fora do catalogo permitido."})
    elif missing := [key for key in trigger.required_config if definition.trigger.config.get(key) in (None, "")]:
        errors.append({"path": "trigger.config", "code": "missing_config", "message": f"Campos obrigatorios: {', '.join(missing)}."})
    for index, condition in enumerate(definition.conditions):
        if condition.operator not in CONDITIONS:
            errors.append({"path": f"conditions.{index}.operator", "code": "unsupported_operator", "message": "Operador fora da whitelist."})
        if not condition.field or condition.field.startswith("_") or "__" in condition.field:
            errors.append({"path": f"conditions.{index}.field", "code": "unsafe_field", "message": "Campo de evento invalido."})
    if not definition.actions:
        errors.append({"path": "actions", "code": "actions_required", "message": "Informe ao menos uma acao."})
    for index, action in enumerate(definition.actions):
        item = ACTIONS.get(action.key)
        if not item:
            errors.append({"path": f"actions.{index}.key", "code": "unsupported_action", "message": "Acao fora da whitelist."})
            continue
        missing = [key for key in item.required_config if action.config.get(key) in (None, "")]
        if missing:
            errors.append({"path": f"actions.{index}.config", "code": "missing_config", "message": f"Campos obrigatorios: {', '.join(missing)}."})
        if action.key.startswith("notification."):
            warnings.append({"path": f"actions.{index}", "code": "contact_policy", "message": "Consentimento, opt-out e rating serao validados no envio."})
    normalized = {
        "trigger": {"key": definition.trigger.key, "config": definition.trigger.config},
        "conditions": [condition.model_dump() for condition in definition.conditions],
        "actions": [action.model_dump() for action in definition.actions],
    }
    return {"valid": not errors, "errors": errors, "warnings": warnings, "normalized": normalized}


def _value(payload: dict[str, Any], path: str) -> Any:
    current: Any = payload
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def conditions_match(conditions: list[Any], payload: dict[str, Any]) -> tuple[bool, list[dict[str, Any]]]:
    steps = []
    matched = True
    for condition in conditions:
        actual = _value(payload, condition.field)
        expected = condition.value
        operator = condition.operator
        try:
            if operator == "eq": result = actual == expected
            elif operator == "neq": result = actual != expected
            elif operator == "in": result = actual in expected if isinstance(expected, (list, tuple, set)) else False
            elif operator == "gt": result = actual > expected
            elif operator == "gte": result = actual >= expected
            elif operator == "lt": result = actual < expected
            elif operator == "lte": result = actual <= expected
            elif operator == "contains": result = expected in actual if isinstance(actual, (str, list, tuple, set)) else False
            elif operator == "exists": result = (actual is not None) == (True if expected is None else bool(expected))
            else: result = False
        except (KeyError, TypeError, ValueError):
            result = False
        matched = matched and result
        steps.append({"type": "condition", "field": condition.field, "operator": operator, "matched": result})
    return matched, steps
