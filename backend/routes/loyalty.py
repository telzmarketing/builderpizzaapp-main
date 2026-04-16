import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.loyalty import LoyaltyLevel, LoyaltyReward, LoyaltyRule, CustomerLoyalty
from backend.schemas.loyalty import (
    LoyaltyLevelCreate, LoyaltyLevelOut,
    LoyaltyRewardCreate, LoyaltyRewardOut,
    LoyaltyRuleCreate, LoyaltyRuleOut,
    CustomerLoyaltyOut, RedeemRewardIn,
)
from backend.services.loyalty_service import redeem_reward

router = APIRouter(prefix="/loyalty", tags=["loyalty"])


# ── Levels ────────────────────────────────────────────────────────────────────

@router.get("/levels", response_model=list[LoyaltyLevelOut])
def list_levels(db: Session = Depends(get_db)):
    return db.query(LoyaltyLevel).order_by(LoyaltyLevel.min_points).all()


@router.post("/levels", response_model=LoyaltyLevelOut, status_code=201)
def create_level(body: LoyaltyLevelCreate, db: Session = Depends(get_db)):
    level = LoyaltyLevel(id=str(uuid.uuid4()), **body.model_dump())
    db.add(level)
    db.commit()
    db.refresh(level)
    return level


@router.put("/levels/{level_id}", response_model=LoyaltyLevelOut)
def update_level(level_id: str, body: LoyaltyLevelCreate, db: Session = Depends(get_db)):
    level = db.query(LoyaltyLevel).filter(LoyaltyLevel.id == level_id).first()
    if not level:
        raise HTTPException(404, "Nível não encontrado.")
    for key, value in body.model_dump().items():
        setattr(level, key, value)
    db.commit()
    db.refresh(level)
    return level


@router.delete("/levels/{level_id}", status_code=204)
def delete_level(level_id: str, db: Session = Depends(get_db)):
    level = db.query(LoyaltyLevel).filter(LoyaltyLevel.id == level_id).first()
    if not level:
        raise HTTPException(404, "Nível não encontrado.")
    db.delete(level)
    db.commit()


# ── Rewards ───────────────────────────────────────────────────────────────────

@router.get("/rewards", response_model=list[LoyaltyRewardOut])
def list_rewards(db: Session = Depends(get_db)):
    return db.query(LoyaltyReward).order_by(LoyaltyReward.points_required).all()


@router.post("/rewards", response_model=LoyaltyRewardOut, status_code=201)
def create_reward(body: LoyaltyRewardCreate, db: Session = Depends(get_db)):
    reward = LoyaltyReward(id=str(uuid.uuid4()), **body.model_dump())
    db.add(reward)
    db.commit()
    db.refresh(reward)
    return reward


@router.put("/rewards/{reward_id}", response_model=LoyaltyRewardOut)
def update_reward(reward_id: str, body: LoyaltyRewardCreate, db: Session = Depends(get_db)):
    reward = db.query(LoyaltyReward).filter(LoyaltyReward.id == reward_id).first()
    if not reward:
        raise HTTPException(404, "Recompensa não encontrada.")
    for key, value in body.model_dump().items():
        setattr(reward, key, value)
    db.commit()
    db.refresh(reward)
    return reward


@router.delete("/rewards/{reward_id}", status_code=204)
def delete_reward(reward_id: str, db: Session = Depends(get_db)):
    reward = db.query(LoyaltyReward).filter(LoyaltyReward.id == reward_id).first()
    if not reward:
        raise HTTPException(404, "Recompensa não encontrada.")
    db.delete(reward)
    db.commit()


# ── Earn Rules ────────────────────────────────────────────────────────────────

@router.get("/rules", response_model=list[LoyaltyRuleOut])
def list_rules(db: Session = Depends(get_db)):
    return db.query(LoyaltyRule).all()


@router.post("/rules", response_model=LoyaltyRuleOut, status_code=201)
def create_rule(body: LoyaltyRuleCreate, db: Session = Depends(get_db)):
    rule = LoyaltyRule(id=str(uuid.uuid4()), **body.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/rules/{rule_id}", status_code=204)
def delete_rule(rule_id: str, db: Session = Depends(get_db)):
    rule = db.query(LoyaltyRule).filter(LoyaltyRule.id == rule_id).first()
    if not rule:
        raise HTTPException(404, "Regra não encontrada.")
    db.delete(rule)
    db.commit()


# ── Customer account ──────────────────────────────────────────────────────────

@router.get("/account/{customer_id}", response_model=CustomerLoyaltyOut)
def get_account(customer_id: str, db: Session = Depends(get_db)):
    account = db.query(CustomerLoyalty).filter(
        CustomerLoyalty.customer_id == customer_id
    ).first()
    if not account:
        raise HTTPException(404, "Conta de fidelidade não encontrada.")
    return account


@router.post("/redeem", status_code=200)
def redeem(body: RedeemRewardIn, db: Session = Depends(get_db)):
    result = redeem_reward(body.customer_id, body.reward_id, db)
    if not result["success"]:
        raise HTTPException(400, result["message"])
    return result
