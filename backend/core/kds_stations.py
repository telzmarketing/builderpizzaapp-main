"""Canonical operational station identifiers and display metadata."""

PIZZA_STATION_IDS = ("pizza-1", "pizza-2")
LEGACY_STATION_IDS = ("pizza", "esfiha", "expedicao")
SUPPORTED_STATION_IDS = PIZZA_STATION_IDS + LEGACY_STATION_IDS
# Display/operational order, not a requirement to assemble every product twice.
# Pizza benches and Esfiha feed the same oven and dispatch workflow.
KDS_OPERATIONAL_ORDER = ("pizza", "esfiha", "forno", "expedicao")
KDS_STATION_LABELS = {
    "pizza-1": "Pizza 1",
    "pizza-2": "Pizza 2",
    "pizza": "Pizza (legado)",
    "esfiha": "Esfiha",
    "expedicao": "Expedição",
}


def station_scope(station_id: str) -> tuple[str, ...]:
    """Return persisted station IDs visible to one KDS station.

    Legacy pizza units remain visible to both fixed pizza benches so existing
    orders are not stranded after the two-bench rollout.
    """
    if station_id in PIZZA_STATION_IDS:
        return (station_id, "pizza")
    return (station_id,)


def is_pizza_station(station_id: str) -> bool:
    return station_id == "pizza" or station_id in PIZZA_STATION_IDS


def is_supported_station(station_id: str | None) -> bool:
    return station_id in SUPPORTED_STATION_IDS


def operational_stage(station_id: str, state: str) -> str | None:
    """Project the current step without changing the unit's assembly station.

    ``station_id`` remains the destination for rework, including legacy pizza
    benches. Oven is an existing attempt state, not another persisted station.
    """
    if state == "cancelled":
        return None
    if state == "ready" or station_id == "expedicao":
        return "expedicao"
    if state in {"baking", "checking"}:
        return "forno"
    return "pizza" if is_pizza_station(station_id) else station_id
