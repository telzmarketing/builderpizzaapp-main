import logging

logger = logging.getLogger("saipos")


def sendOrderToSaipos(order_id: str) -> None:
    """Stub for sending an approved order to Saipos."""
    logger.info("[SAIPOS] sendOrderToSaipos called for order=%s", order_id)
