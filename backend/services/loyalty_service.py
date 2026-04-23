"""
Loyalty Engine — Retention Engine Pro
- Monthly cycles with 50% point rollover
- 4 tiers: Bronze, Prata, Ouro, Diamante
- Level-specific benefits (product, discount, frete_gratis, experience)
- Referral system (10pts per referral)
- Onboarding: Aventureiro → Explorador
- Event publishing after every state change
"""
import uuid
import random
import string
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.models.loyalty import (
    CustomerLoyalty, LoyaltyLevel, LoyaltyReward, LoyaltyTransaction,
    LoyaltyBenefit, LoyaltyBenefitUsage, LoyaltyCycle, Referral,
    TransactionType, CycleStatus, ReferralStatus,
)
from backend.config import get_settings
from backend.core.events import (
    bus,
    LoyaltyPointsEarned, LoyaltyLevelUp,
    LoyaltyBenefitUnlocked, LoyaltyBenefitUsed,
    LoyaltyCycleStarted, LoyaltyCycleClosed, PointsExpiringSoon,
)

settings = get_settings()

CYCLE_DAYS = 30
ROLLOVER_RATIO = 0.5  # 50% of remaining points carry forward
REFERRAL_POINTS = 10


# ── Internal helpers ──────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_or_create_account(customer_id: str, db: Session) -> CustomerLoyalty:
    account = db.query(CustomerLoyalty).filter(
        CustomerLoyalty.customer_id == customer_id
    ).first()
    if not account:
        now = _now()
        account = CustomerLoyalty(
            id=str(uuid.uuid4()),
            customer_id=customer_id,
            total_points=0,
            rollover_points=0,
            lifetime_points=0,
            cycle_start_date=now,
            cycle_end_date=now + timedelta(days=CYCLE_DAYS),
            last_activity_at=now,
        )
        db.add(account)
        db.flush()
        _open_cycle(account, db)
    return account


def _open_cycle(account: CustomerLoyalty, db: Session) -> LoyaltyCycle:
    """Create a new cycle record for the account."""
    now = _now()
    cycle = LoyaltyCycle(
        id=str(uuid.uuid4()),
        customer_id=account.customer_id,
        start_date=account.cycle_start_date or now,
        end_date=account.cycle_end_date or (now + timedelta(days=CYCLE_DAYS)),
        points_earned=0,
        points_used=0,
        points_expired=0,
        points_rolled_over=0,
        level_reached=account.level_id,
        status=CycleStatus.active,
    )
    db.add(cycle)
    db.flush()
    bus.publish(LoyaltyCycleStarted(
        customer_id=account.customer_id,
        cycle_id=cycle.id,
        start_date=str(cycle.start_date),
        end_date=str(cycle.end_date),
    ))
    return cycle


def _get_active_cycle(account: CustomerLoyalty, db: Session) -> Optional[LoyaltyCycle]:
    return db.query(LoyaltyCycle).filter(
        LoyaltyCycle.customer_id == account.customer_id,
        LoyaltyCycle.status == CycleStatus.active,
    ).order_by(LoyaltyCycle.start_date.desc()).first()


def _close_cycle_if_expired(account: CustomerLoyalty, db: Session) -> None:
    """Check if cycle is expired and roll over points if needed."""
    if not account.cycle_end_date:
        return
    now = _now()
    end = account.cycle_end_date
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    if now < end:
        return

    cycle = _get_active_cycle(account, db)
    remaining = account.total_points
    rolled_over = int(remaining * ROLLOVER_RATIO)
    expired = remaining - rolled_over

    if cycle:
        cycle.points_expired = expired
        cycle.points_rolled_over = rolled_over
        cycle.status = CycleStatus.closed
        cycle.closed_at = now
        db.flush()
        bus.publish(LoyaltyCycleClosed(
            customer_id=account.customer_id,
            cycle_id=cycle.id,
            points_earned=cycle.points_earned,
            points_rolled_over=rolled_over,
            points_expired=expired,
        ))

    if expired > 0:
        db.add(LoyaltyTransaction(
            id=str(uuid.uuid4()),
            customer_loyalty_id=account.id,
            points=-expired,
            transaction_type=TransactionType.expired,
            description="Pontos expirados — fim do ciclo mensal",
        ))
    if rolled_over > 0:
        db.add(LoyaltyTransaction(
            id=str(uuid.uuid4()),
            customer_loyalty_id=account.id,
            points=rolled_over,
            transaction_type=TransactionType.rollover,
            description=f"Rollover 50% do ciclo anterior ({expired} expirados)",
        ))

    account.total_points = rolled_over
    account.rollover_points = rolled_over
    account.cycle_start_date = now
    account.cycle_end_date = now + timedelta(days=CYCLE_DAYS)
    db.flush()
    _open_cycle(account, db)


def _update_level(account: CustomerLoyalty, db: Session) -> None:
    """Promote or demote the customer to the correct loyalty level."""
    prev_level_id = account.level_id
    levels: list[LoyaltyLevel] = (
        db.query(LoyaltyLevel)
        .order_by(LoyaltyLevel.min_points.desc())
        .all()
    )
    new_level_id = None
    for level in levels:
        if account.total_points >= level.min_points:
            new_level_id = level.id
            break
    account.level_id = new_level_id

    if new_level_id and new_level_id != prev_level_id and prev_level_id is not None:
        prev_name = next((l.name for l in levels if l.id == prev_level_id), "")
        new_name = next((l.name for l in levels if l.id == new_level_id), "")
        bus.publish(LoyaltyLevelUp(
            customer_id=account.customer_id,
            from_level=prev_name,
            to_level=new_name,
            total_points=account.total_points,
        ))
        # Notify about newly unlocked benefits
        benefits = db.query(LoyaltyBenefit).filter(
            LoyaltyBenefit.level_id == new_level_id,
            LoyaltyBenefit.active == True,  # noqa: E712
        ).all()
        level_obj = next((l for l in levels if l.id == new_level_id), None)
        for b in benefits:
            bus.publish(LoyaltyBenefitUnlocked(
                customer_id=account.customer_id,
                benefit_id=b.id,
                benefit_label=b.label,
                level_name=level_obj.name if level_obj else "",
            ))


def _add_points(account: CustomerLoyalty, points: int, tx_type: TransactionType,
                description: str, order_id: Optional[str], db: Session) -> None:
    account.total_points += points
    if tx_type in (TransactionType.earned, TransactionType.referral,
                   TransactionType.bonus, TransactionType.manual):
        account.lifetime_points = (account.lifetime_points or 0) + max(0, points)
    account.last_activity_at = _now()

    # Update active cycle earned total
    cycle = _get_active_cycle(account, db)
    if cycle and points > 0:
        cycle.points_earned += points
    elif cycle and points < 0 and tx_type == TransactionType.redeemed:
        cycle.points_used += abs(points)

    db.add(LoyaltyTransaction(
        id=str(uuid.uuid4()),
        customer_loyalty_id=account.id,
        order_id=order_id,
        points=points,
        transaction_type=tx_type,
        description=description,
    ))


# ── Public API ────────────────────────────────────────────────────────────────

def award_points_for_order(customer_id: str, order_id: str, order_total: float, db: Session) -> int:
    """Award points based on order total. Returns points awarded."""
    points = int(order_total * settings.POINTS_PER_REAL) + settings.DELIVERY_POINTS

    account = _get_or_create_account(customer_id, db)
    _close_cycle_if_expired(account, db)

    _add_points(account, points, TransactionType.earned,
                f"Pedido #{order_id[:8]} entregue", order_id, db)
    _update_level(account, db)
    db.commit()

    bus.publish(LoyaltyPointsEarned(
        customer_id=customer_id,
        points=points,
        reason="order",
        total_points=account.total_points,
    ))
    return points


def redeem_reward(customer_id: str, reward_id: str, db: Session) -> dict:
    reward = db.query(LoyaltyReward).filter(
        LoyaltyReward.id == reward_id, LoyaltyReward.active == True  # noqa: E712
    ).first()
    if not reward:
        return {"success": False, "message": "Recompensa não encontrada."}

    account = _get_or_create_account(customer_id, db)
    _close_cycle_if_expired(account, db)
    if account.total_points < reward.points_required:
        return {"success": False, "message": "Pontos insuficientes."}

    _add_points(account, -reward.points_required, TransactionType.redeemed,
                f"Resgate: {reward.label}", None, db)
    _update_level(account, db)
    db.commit()
    return {"success": True, "message": f"Recompensa '{reward.label}' resgatada com sucesso!"}


def redeem_benefit(customer_id: str, benefit_id: str, order_id: Optional[str], db: Session) -> dict:
    """Redeem a level benefit (product, discount, frete_gratis, experience)."""
    account = _get_or_create_account(customer_id, db)
    _close_cycle_if_expired(account, db)

    benefit = db.query(LoyaltyBenefit).filter(
        LoyaltyBenefit.id == benefit_id, LoyaltyBenefit.active == True  # noqa: E712
    ).first()
    if not benefit:
        return {"success": False, "message": "Benefício não encontrado."}

    # Must be at required level or higher
    customer_level = db.query(LoyaltyLevel).filter(
        LoyaltyLevel.id == account.level_id
    ).first()
    benefit_level = db.query(LoyaltyLevel).filter(
        LoyaltyLevel.id == benefit.level_id
    ).first()
    if not customer_level or not benefit_level:
        return {"success": False, "message": "Nível de fidelidade não encontrado."}
    if customer_level.min_points < benefit_level.min_points:
        return {"success": False, "message": f"Benefício exclusivo para {benefit_level.name} ou superior."}

    # Check usage limit in current cycle
    cycle_start = account.cycle_start_date or (_now() - timedelta(days=CYCLE_DAYS))
    if cycle_start.tzinfo is None:
        cycle_start = cycle_start.replace(tzinfo=timezone.utc)
    usage_count = db.query(func.count(LoyaltyBenefitUsage.id)).filter(
        LoyaltyBenefitUsage.customer_id == customer_id,
        LoyaltyBenefitUsage.benefit_id == benefit_id,
        LoyaltyBenefitUsage.used_at >= cycle_start,
    ).scalar() or 0
    if usage_count >= benefit.usage_limit:
        return {"success": False, "message": "Limite de uso deste benefício atingido para o ciclo atual."}

    usage = LoyaltyBenefitUsage(
        id=str(uuid.uuid4()),
        customer_id=customer_id,
        benefit_id=benefit_id,
        order_id=order_id,
    )
    db.add(usage)
    db.commit()

    bus.publish(LoyaltyBenefitUsed(
        customer_id=customer_id,
        benefit_id=benefit_id,
        benefit_label=benefit.label,
        order_id=order_id,
    ))
    return {"success": True, "message": f"Benefício '{benefit.label}' aplicado!", "benefit": benefit}


def get_customer_account(customer_id: str, db: Session) -> Optional[CustomerLoyalty]:
    """Return full loyalty account, ticking the cycle engine."""
    account = db.query(CustomerLoyalty).filter(
        CustomerLoyalty.customer_id == customer_id
    ).first()
    if not account:
        return None
    _close_cycle_if_expired(account, db)
    db.commit()
    return account


def get_available_benefits(customer_id: str, db: Session) -> list[LoyaltyBenefit]:
    """Return benefits available to the customer's current level."""
    account = db.query(CustomerLoyalty).filter(
        CustomerLoyalty.customer_id == customer_id
    ).first()
    if not account or not account.level_id:
        return []
    customer_level = db.query(LoyaltyLevel).filter(
        LoyaltyLevel.id == account.level_id
    ).first()
    if not customer_level:
        return []
    # All levels whose min_points <= customer's level
    eligible_level_ids = [
        l.id for l in db.query(LoyaltyLevel).filter(
            LoyaltyLevel.min_points <= customer_level.min_points
        ).all()
    ]
    return db.query(LoyaltyBenefit).filter(
        LoyaltyBenefit.level_id.in_(eligible_level_ids),
        LoyaltyBenefit.active == True,  # noqa: E712
    ).all()


def award_manual_points(customer_id: str, points: int, description: str, db: Session) -> dict:
    """Admin: manually add or subtract points."""
    account = _get_or_create_account(customer_id, db)
    _close_cycle_if_expired(account, db)
    new_total = account.total_points + points
    if new_total < 0:
        return {"success": False, "message": "Operação resultaria em saldo negativo."}

    _add_points(account, points, TransactionType.manual, description, None, db)
    _update_level(account, db)
    db.commit()

    if points > 0:
        bus.publish(LoyaltyPointsEarned(
            customer_id=customer_id,
            points=points,
            reason="manual",
            total_points=account.total_points,
        ))
    return {"success": True, "total_points": account.total_points}


def admin_close_cycle(customer_id: str, db: Session) -> dict:
    """Admin: manually close the current cycle for a customer."""
    account = db.query(CustomerLoyalty).filter(
        CustomerLoyalty.customer_id == customer_id
    ).first()
    if not account:
        return {"success": False, "message": "Cliente não encontrado."}
    # Force expiry by pushing end_date to the past
    account.cycle_end_date = _now() - timedelta(seconds=1)
    db.flush()
    _close_cycle_if_expired(account, db)
    _update_level(account, db)
    db.commit()
    return {"success": True, "message": "Ciclo encerrado e rollover aplicado."}


# ── Referral system ───────────────────────────────────────────────────────────

def _generate_referral_code(length: int = 8) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


def get_or_create_referral_code(customer_id: str, db: Session) -> Referral:
    ref = db.query(Referral).filter(
        Referral.referrer_id == customer_id,
        Referral.status == ReferralStatus.pending,
        Referral.referred_id == None,  # noqa: E711
    ).first()
    if ref:
        return ref

    code = _generate_referral_code()
    while db.query(Referral).filter(Referral.referral_code == code).first():
        code = _generate_referral_code()

    ref = Referral(
        id=str(uuid.uuid4()),
        referrer_id=customer_id,
        referral_code=code,
        reward_points=REFERRAL_POINTS,
        status=ReferralStatus.pending,
    )
    db.add(ref)
    db.commit()
    return ref


def complete_referral(referral_code: str, referred_customer_id: str, db: Session) -> dict:
    ref = db.query(Referral).filter(
        Referral.referral_code == referral_code,
        Referral.status == ReferralStatus.pending,
    ).first()
    if not ref:
        return {"success": False, "message": "Código de indicação inválido."}
    if ref.referrer_id == referred_customer_id:
        return {"success": False, "message": "Você não pode usar seu próprio código."}
    if ref.referred_id:
        return {"success": False, "message": "Código já utilizado."}

    ref.referred_id = referred_customer_id
    ref.status = ReferralStatus.completed
    ref.completed_at = _now()

    # Award referrer
    referrer_account = _get_or_create_account(ref.referrer_id, db)
    _add_points(referrer_account, REFERRAL_POINTS, TransactionType.referral,
                "Indicação completada", None, db)
    _update_level(referrer_account, db)

    # Award referred customer (also gets points for signing up via referral)
    referred_account = _get_or_create_account(referred_customer_id, db)
    _add_points(referred_account, REFERRAL_POINTS, TransactionType.referral,
                "Cadastro via indicação", None, db)
    _update_level(referred_account, db)

    db.commit()
    return {"success": True, "message": f"Indicação confirmada! +{REFERRAL_POINTS} pontos para ambos."}
