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
import json
import urllib.request
import urllib.error

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.core.response import ok, created, err_msg
from backend.database import get_db
from backend.models.customer import Customer, Address
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


class GoogleLoginIn(BaseModel):
    credential: str = Field(..., description="Google ID token from GSI")


class EmailLoginIn(BaseModel):
    email: str = Field(..., min_length=5, description="Customer email address")


class RegisterIn(BaseModel):
    name: str = Field(..., min_length=2)
    email: str = Field(..., min_length=5)
    phone: str = Field(..., min_length=8)
    street: str = Field(..., min_length=3)
    number: str = Field(..., min_length=1)
    complement: str | None = None
    neighborhood: str = Field(..., min_length=2)
    city: str = Field(..., min_length=2)
    state: str | None = None
    zip_code: str = Field(..., min_length=8)
    label: str | None = None
    lgpd_consent: bool = Field(..., description="Must be True to complete registration")
    lgpd_policy_version: str | None = None
    marketing_email_consent: bool = False
    marketing_whatsapp_consent: bool = False


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


@router.post("/login-email")
def login_email(body: EmailLoginIn, db: Session = Depends(get_db)):
    """Login by email or phone for registered customers."""
    identifier = body.email.strip()
    # Detect phone vs email
    if "@" in identifier:
        email = identifier.lower()
        customer = db.query(Customer).filter(Customer.email == email).first()
        if not customer:
            return err_msg(
                "E-mail não encontrado. Crie sua conta primeiro.",
                code="EmailNotFound",
                status_code=404,
            )
    else:
        phone = _normalize_phone(identifier)
        customer = _find_by_phone(phone, db)
        if not customer:
            return err_msg(
                "Telefone não encontrado. Crie sua conta primeiro.",
                code="PhoneNotFound",
                status_code=404,
            )
    return ok(LoginOut(customer=CustomerOut.model_validate(customer), is_new=False),
              f"Bem-vindo de volta, {customer.name}!")


@router.post("/register")
def register(body: RegisterIn, db: Session = Depends(get_db)):
    """Full registration: name, email, phone + delivery address + LGPD consent."""
    if not body.lgpd_consent:
        return err_msg(
            "É necessário aceitar os Termos de Privacidade para criar a conta.",
            code="LgpdRequired",
            status_code=422,
        )

    email = body.email.strip().lower()
    phone = _normalize_phone(body.phone)

    if db.query(Customer).filter(Customer.email == email).first():
        return err_msg(
            "E-mail já cadastrado. Tente fazer login.",
            code="EmailTaken",
            status_code=409,
        )
    if phone and db.query(Customer).filter(Customer.phone == phone).first():
        return err_msg(
            "Telefone já cadastrado. Tente fazer login.",
            code="PhoneTaken",
            status_code=409,
        )

    from datetime import datetime, timezone as tz
    now = datetime.now(tz.utc)

    new_customer = Customer(
        id=str(uuid.uuid4()),
        name=body.name.strip(),
        email=email,
        phone=phone,
        lgpd_consent=True,
        lgpd_consent_at=now,
        lgpd_policy_version=body.lgpd_policy_version,
        marketing_email_consent=body.marketing_email_consent,
        marketing_whatsapp_consent=body.marketing_whatsapp_consent,
    )
    db.add(new_customer)
    db.flush()

    new_address = Address(
        id=str(uuid.uuid4()),
        customer_id=new_customer.id,
        label=body.label,
        street=body.street.strip(),
        number=body.number,
        complement=body.complement,
        neighborhood=body.neighborhood,
        city=body.city.strip(),
        state=body.state,
        zip_code=body.zip_code,
        is_default=True,
    )
    db.add(new_address)
    db.commit()
    db.refresh(new_customer)

    return created(
        LoginOut(customer=CustomerOut.model_validate(new_customer), is_new=True),
        f"Conta criada! Bem-vindo, {new_customer.name}!",
    )


@router.post("/google")
def google_login(body: GoogleLoginIn, db: Session = Depends(get_db)):
    """
    Verify a Google ID token from the GSI client and return (or create) a customer.
    The token is verified by calling Google's tokeninfo endpoint.
    """
    # Verify token with Google
    try:
        url = f"https://oauth2.googleapis.com/tokeninfo?id_token={body.credential}"
        with urllib.request.urlopen(url, timeout=10) as resp:
            payload = json.loads(resp.read())
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=401, detail="Token Google inválido ou expirado.") from exc

    google_sub = payload.get("sub")
    email = payload.get("email")
    name = payload.get("name") or payload.get("given_name") or "Cliente"

    if not google_sub or not email:
        raise HTTPException(status_code=401, detail="Token Google não contém dados suficientes.")

    # Find existing customer by google_id first, then by email
    customer = (
        db.query(Customer).filter(Customer.google_id == google_sub).first()
        or db.query(Customer).filter(Customer.email == email).first()
    )

    if customer:
        # Link google_id if not set yet (first Google login on phone-created account)
        if not customer.google_id:
            customer.google_id = google_sub
            db.commit()
            db.refresh(customer)
        result = LoginOut(customer=CustomerOut.model_validate(customer), is_new=False)
        return ok(result, f"Bem-vindo de volta, {customer.name}!")

    # Create new customer from Google
    new_customer = Customer(
        id=str(uuid.uuid4()),
        name=name,
        email=email,
        google_id=google_sub,
    )
    db.add(new_customer)
    db.commit()
    db.refresh(new_customer)

    result = LoginOut(customer=CustomerOut.model_validate(new_customer), is_new=True)
    return created(result, f"Bem-vindo, {new_customer.name}!")
