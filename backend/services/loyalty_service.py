"""
Loyalty engine:
  - Award points when an order is delivered.
  - Upgrade level automatically.
  - Allow reward redemption.
"""
import uuid
from sqlalchemy.orm import Session

from backend.models.loyalty import (
    CustomerLoyalty, LoyaltyLevel, LoyaltyReward, LoyaltyTransaction, TransactionType
)
from backend.config import get_settings

settings = get_settings()


def _get_or_create_account(customer_id: str, db: Session) -> CustomerLoyalty:
    account = db.query(CustomerLoyalty).filter(
        CustomerLoyalty.customer_id == customer_id
    ).first()
    if not account:
        account = CustomerLoyalty(
            id=str(uuid.uuid4()),
            customer_id=customer_id,
            total_points=0,
        )
        db.add(account)
        db.flush()
    return account


def _update_level(account: CustomerLoyalty, db: Session) -> None:
    """Promote or demote the customer to the correct loyalty level."""
    levels: list[LoyaltyLevel] = (
        db.query(LoyaltyLevel)
        .order_by(LoyaltyLevel.min_points.desc())
        .all()
    )
    for level in levels:
        if account.total_points >= level.min_points:
            account.level_id = level.id
            return
    account.level_id = None


def award_points_for_order(customer_id: str, order_id: str, order_total: float, db: Session) -> int:
    """Award points based on order total. Returns points awarded."""
    points = int(order_total * settings.POINTS_PER_REAL) + settings.DELIVERY_POINTS

    account = _get_or_create_account(customer_id, db)
    account.total_points += points

    tx = LoyaltyTransaction(
        id=str(uuid.uuid4()),
        customer_loyalty_id=account.id,
        order_id=order_id,
        points=points,
        transaction_type=TransactionType.earned,
        description=f"Pedido #{order_id[:8]} entregue",
    )
    db.add(tx)
    _update_level(account, db)
    db.commit()
    return points


def redeem_reward(customer_id: str, reward_id: str, db: Session) -> dict:
    reward = db.query(LoyaltyReward).filter(
        LoyaltyReward.id == reward_id, LoyaltyReward.active == True  # noqa: E712
    ).first()
    if not reward:
        return {"success": False, "message": "Recompensa não encontrada."}

    account = _get_or_create_account(customer_id, db)
    if account.total_points < reward.points_required:
        return {"success": False, "message": "Pontos insuficientes."}

    account.total_points -= reward.points_required
    tx = LoyaltyTransaction(
        id=str(uuid.uuid4()),
        customer_loyalty_id=account.id,
        points=-reward.points_required,
        transaction_type=TransactionType.redeemed,
        description=f"Resgate: {reward.label}",
    )
    db.add(tx)
    _update_level(account, db)
    db.commit()
    return {"success": True, "message": f"Recompensa '{reward.label}' resgatada com sucesso!"}
