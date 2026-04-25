import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.loyalty import (
    LoyaltyLevel, LoyaltyReward, LoyaltyRule, CustomerLoyalty,
    LoyaltyBenefit, LoyaltyCycle, Referral,
)
from backend.routes.admin_auth import get_current_admin
from backend.schemas.loyalty import (
    LoyaltyLevelCreate, LoyaltyLevelOut,
    LoyaltyRewardCreate, LoyaltyRewardOut,
    LoyaltyRuleCreate, LoyaltyRuleOut,
    LoyaltySettingsUpdate, LoyaltySettingsOut,
    LoyaltyBenefitCreate, LoyaltyBenefitOut,
    LoyaltyCycleOut, ReferralOut,
    CustomerLoyaltyOut, RedeemRewardIn,
    RedeemBenefitIn, ManualPointsIn,
)
from backend.services.loyalty_service import (
    redeem_reward, redeem_benefit, get_customer_account,
    get_available_benefits, award_manual_points, admin_close_cycle,
    get_or_create_referral_code, complete_referral,
    get_loyalty_settings,
)

router = APIRouter(prefix="/loyalty", tags=["loyalty"])


@router.get("/settings", response_model=LoyaltySettingsOut)
def read_settings(db: Session = Depends(get_db)):
    return get_loyalty_settings(db)


@router.put("/settings", response_model=LoyaltySettingsOut)
def update_settings(
    body: LoyaltySettingsUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    settings = get_loyalty_settings(db)
    settings.enabled = body.enabled
    settings.points_per_real = body.points_per_real
    db.commit()
    db.refresh(settings)
    return settings


# ── Levels ────────────────────────────────────────────────────────────────────

@router.get("/levels", response_model=List[LoyaltyLevelOut])
def list_levels(db: Session = Depends(get_db)):
    return db.query(LoyaltyLevel).order_by(LoyaltyLevel.min_points).all()


@router.post("/levels", response_model=LoyaltyLevelOut, status_code=201)
def create_level(body: LoyaltyLevelCreate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    level = LoyaltyLevel(id=str(uuid.uuid4()), **body.model_dump())
    db.add(level)
    db.commit()
    db.refresh(level)
    return level


@router.put("/levels/{level_id}", response_model=LoyaltyLevelOut)
def update_level(level_id: str, body: LoyaltyLevelCreate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    level = db.query(LoyaltyLevel).filter(LoyaltyLevel.id == level_id).first()
    if not level:
        raise HTTPException(404, "Nível não encontrado.")
    for key, value in body.model_dump().items():
        setattr(level, key, value)
    db.commit()
    db.refresh(level)
    return level


@router.delete("/levels/{level_id}", status_code=204)
def delete_level(level_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    level = db.query(LoyaltyLevel).filter(LoyaltyLevel.id == level_id).first()
    if not level:
        raise HTTPException(404, "Nível não encontrado.")
    db.delete(level)
    db.commit()


# ── Benefits ──────────────────────────────────────────────────────────────────

@router.get("/benefits", response_model=List[LoyaltyBenefitOut])
def list_benefits(level_id: Optional[str] = Query(None), db: Session = Depends(get_db)):
    q = db.query(LoyaltyBenefit)
    if level_id:
        q = q.filter(LoyaltyBenefit.level_id == level_id)
    return q.order_by(LoyaltyBenefit.level_id).all()


@router.post("/benefits", response_model=LoyaltyBenefitOut, status_code=201)
def create_benefit(body: LoyaltyBenefitCreate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    benefit = LoyaltyBenefit(id=str(uuid.uuid4()), **body.model_dump())
    db.add(benefit)
    db.commit()
    db.refresh(benefit)
    return benefit


@router.put("/benefits/{benefit_id}", response_model=LoyaltyBenefitOut)
def update_benefit(benefit_id: str, body: LoyaltyBenefitCreate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    benefit = db.query(LoyaltyBenefit).filter(LoyaltyBenefit.id == benefit_id).first()
    if not benefit:
        raise HTTPException(404, "Benefício não encontrado.")
    for key, value in body.model_dump().items():
        setattr(benefit, key, value)
    db.commit()
    db.refresh(benefit)
    return benefit


@router.delete("/benefits/{benefit_id}", status_code=204)
def delete_benefit(benefit_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    benefit = db.query(LoyaltyBenefit).filter(LoyaltyBenefit.id == benefit_id).first()
    if not benefit:
        raise HTTPException(404, "Benefício não encontrado.")
    db.delete(benefit)
    db.commit()


@router.post("/benefits/redeem")
def use_benefit(body: RedeemBenefitIn, db: Session = Depends(get_db)):
    if not get_loyalty_settings(db).enabled:
        raise HTTPException(403, "Programa de fidelidade desativado.")
    result = redeem_benefit(body.customer_id, body.benefit_id, body.order_id, db)
    if not result["success"]:
        raise HTTPException(400, result["message"])
    return result


# ── Rewards ───────────────────────────────────────────────────────────────────

@router.get("/rewards", response_model=List[LoyaltyRewardOut])
def list_rewards(db: Session = Depends(get_db)):
    return db.query(LoyaltyReward).order_by(LoyaltyReward.points_required).all()


@router.post("/rewards", response_model=LoyaltyRewardOut, status_code=201)
def create_reward(body: LoyaltyRewardCreate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    reward = LoyaltyReward(id=str(uuid.uuid4()), **body.model_dump())
    db.add(reward)
    db.commit()
    db.refresh(reward)
    return reward


@router.put("/rewards/{reward_id}", response_model=LoyaltyRewardOut)
def update_reward(reward_id: str, body: LoyaltyRewardCreate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    reward = db.query(LoyaltyReward).filter(LoyaltyReward.id == reward_id).first()
    if not reward:
        raise HTTPException(404, "Recompensa não encontrada.")
    for key, value in body.model_dump().items():
        setattr(reward, key, value)
    db.commit()
    db.refresh(reward)
    return reward


@router.delete("/rewards/{reward_id}", status_code=204)
def delete_reward(reward_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    reward = db.query(LoyaltyReward).filter(LoyaltyReward.id == reward_id).first()
    if not reward:
        raise HTTPException(404, "Recompensa não encontrada.")
    db.delete(reward)
    db.commit()


# ── Earn Rules ────────────────────────────────────────────────────────────────

@router.get("/rules", response_model=List[LoyaltyRuleOut])
def list_rules(db: Session = Depends(get_db)):
    return db.query(LoyaltyRule).all()


@router.post("/rules", response_model=LoyaltyRuleOut, status_code=201)
def create_rule(body: LoyaltyRuleCreate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    rule = LoyaltyRule(id=str(uuid.uuid4()), **body.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/rules/{rule_id}", status_code=204)
def delete_rule(rule_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    rule = db.query(LoyaltyRule).filter(LoyaltyRule.id == rule_id).first()
    if not rule:
        raise HTTPException(404, "Regra não encontrada.")
    db.delete(rule)
    db.commit()


# ── Customer account ──────────────────────────────────────────────────────────

@router.get("/account/{customer_id}", response_model=CustomerLoyaltyOut)
def get_account(customer_id: str, db: Session = Depends(get_db)):
    if not get_loyalty_settings(db).enabled:
        raise HTTPException(403, "Programa de fidelidade desativado.")
    account = get_customer_account(customer_id, db)
    if not account:
        raise HTTPException(404, "Conta de fidelidade não encontrada.")
    # Attach available benefits and cycles for full response
    account.benefits = get_available_benefits(customer_id, db)
    account.cycles = (
        db.query(LoyaltyCycle)
        .filter(LoyaltyCycle.customer_id == customer_id)
        .order_by(LoyaltyCycle.start_date.desc())
        .limit(12)
        .all()
    )
    return account


@router.post("/redeem", status_code=200)
def redeem(body: RedeemRewardIn, db: Session = Depends(get_db)):
    if not get_loyalty_settings(db).enabled:
        raise HTTPException(403, "Programa de fidelidade desativado.")
    result = redeem_reward(body.customer_id, body.reward_id, db)
    if not result["success"]:
        raise HTTPException(400, result["message"])
    return result


# ── Admin controls ────────────────────────────────────────────────────────────

@router.get("/admin/customers", response_model=List[CustomerLoyaltyOut])
def list_loyalty_customers(
    level_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    q = db.query(CustomerLoyalty)
    if level_id:
        q = q.filter(CustomerLoyalty.level_id == level_id)
    return q.order_by(CustomerLoyalty.total_points.desc()).limit(200).all()


@router.post("/admin/points")
def admin_points(body: ManualPointsIn, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    if not get_loyalty_settings(db).enabled:
        raise HTTPException(403, "Programa de fidelidade desativado.")
    result = award_manual_points(body.customer_id, body.points, body.description, db)
    if not result["success"]:
        raise HTTPException(400, result["message"])
    return result


@router.post("/admin/close-cycle")
def admin_cycle(body: dict, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    customer_id = body.get("customer_id")
    if not customer_id:
        raise HTTPException(422, "customer_id obrigatório.")
    result = admin_close_cycle(customer_id, db)
    if not result["success"]:
        raise HTTPException(400, result["message"])
    return result


@router.get("/admin/cycles/{customer_id}", response_model=List[LoyaltyCycleOut])
def list_cycles(customer_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    return (
        db.query(LoyaltyCycle)
        .filter(LoyaltyCycle.customer_id == customer_id)
        .order_by(LoyaltyCycle.start_date.desc())
        .all()
    )


# ── Referrals ─────────────────────────────────────────────────────────────────

@router.get("/referral/{customer_id}", response_model=ReferralOut)
def get_referral(customer_id: str, db: Session = Depends(get_db)):
    if not get_loyalty_settings(db).enabled:
        raise HTTPException(403, "Programa de fidelidade desativado.")
    ref = get_or_create_referral_code(customer_id, db)
    return ref


@router.post("/referral/complete")
def complete_ref(body: dict, db: Session = Depends(get_db)):
    if not get_loyalty_settings(db).enabled:
        raise HTTPException(403, "Programa de fidelidade desativado.")
    code = body.get("referral_code")
    referred_id = body.get("customer_id")
    if not code or not referred_id:
        raise HTTPException(422, "referral_code e customer_id obrigatórios.")
    result = complete_referral(code, referred_id, db)
    if not result["success"]:
        raise HTTPException(400, result["message"])
    return result
