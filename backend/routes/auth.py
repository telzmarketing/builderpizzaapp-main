"""
Auth endpoints — phone-based identification (no JWT required for v1).

Used by the loja to link orders to customer accounts.

Flow:
  1. Loja calls POST /auth/check-phone with the customer's phone.
  2. If customer exists → return their profile.
  3. If not          → loja prompts for name, then calls POST /auth/login.
  4. /auth/login creates the customer (if new) or returns the existing one.

Both endpoints are idempotent — safe to call multiple times.
"""
from __future__ import annotations

import uuid
import re

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.core.response import ok, created, err_msg
from backend.database import get_db
from backend.models.customer import Customer
from backend.schemas.customer import CustomerOut

router = APIRouter(prefix="/auth", tags=["auth"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _normalize_phone(phone: str) -> str:
    """Strip everything except digits and leading +."""
    digits = re.sub(r"[^\d+]", "", phone)
    return digits


def _find_by_phone(phone: str, db: Session) -> Customer | None:
    normalized = _normalize_phone(phone)
    return (
        db.query(Customer)
        .filter(Customer.phone == normalized)
        .first()
    )


# ── Schemas ───────────────────────────────────────────────────────────────────

class CheckPhoneIn(BaseModel):
    phone: str = Field(..., min_length=8, description="Customer phone number")


class CheckPhoneOut(BaseModel):
    exists: bool
    customer_id: str | None = None
    name: str | None = None


class LoginIn(BaseModel):
    phone: str = Field(..., min_length=8)
    name: str | None = Field(
        default=None,
        description="Required when creating a new account (customer not found by phone)"
    )


class LoginOut(BaseModel):
    customer: CustomerOut
    is_new: bool = False   # True if account was just created in this call


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/check-phone")
def check_phone(body: CheckPhoneIn, db: Session = Depends(get_db)):
    """
    Check whether a phone number belongs to a registered customer.

    Used by the loja checkout to decide:
      - exists=true  → greet the customer by name, skip registration form
      - exists=false → show name input, then call POST /auth/login

    Does NOT create any record. Safe to call at any time.

    Response:
      { "success": true, "data": { "exists": bool, "customer_id": "...", "name": "..." } }
    """
    customer = _find_by_phone(body.phone, db)
    if customer:
        result = CheckPhoneOut(
            exists=True,
            customer_id=customer.id,
            name=customer.name,
        )
    else:
        result = CheckPhoneOut(exists=False)

    return ok(result)


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    """
    Find or create a customer account by phone number.

    - If a customer with this phone already exists → return their profile.
    - If not → create a new customer (requires `name` in the body).

    This is a simplified auth suitable for delivery apps where the phone
    is the primary identifier. Add JWT / OTP in a future version.

    Response:
      {
        "success": true,
        "data": {
          "customer": { ...CustomerOut... },
          "is_new": false
        },
        "message": "Bem-vindo de volta, João!"
      }
    """
    normalized = _normalize_phone(body.phone)
    customer = _find_by_phone(normalized, db)

    if customer:
        result = LoginOut(customer=CustomerOut.model_validate(customer), is_new=False)
        return ok(result, f"Bem-vindo de volta, {customer.name}!")

    # New customer — name is required
    if not body.name or not body.name.strip():
        return err_msg(
            "Número não cadastrado. Informe seu nome para criar a conta.",
            code="NameRequired",
            status_code=422,
        )

    new_customer = Customer(
        id=str(uuid.uuid4()),
        name=body.name.strip(),
        email=f"{normalized}@phone.pizzaapp",   # placeholder — not used for auth
        phone=normalized,
    )
    db.add(new_customer)
    db.commit()
    db.refresh(new_customer)

    result = LoginOut(
        customer=CustomerOut.model_validate(new_customer),
        is_new=True,
    )
    return created(result, f"Conta criada! Bem-vindo, {new_customer.name}!")
