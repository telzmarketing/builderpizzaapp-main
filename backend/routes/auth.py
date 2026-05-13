from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.core.response import created, err_msg, ok
from backend.core.security import hash_password, verify_password
from backend.database import get_db
from backend.models.customer import Address, Customer
from backend.schemas.customer import CustomerOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _normalize_phone(phone: str) -> str:
    return re.sub(r"[^\d+]", "", phone)


def _find_by_phone(phone: str, db: Session) -> Customer | None:
    normalized = _normalize_phone(phone)
    return db.query(Customer).filter(Customer.phone == normalized).first()


def _verify_or_activate_password(customer: Customer, password: str, db: Session) -> tuple[bool, bool]:
    """
    Return (authenticated, password_was_created).

    Legacy customers may exist without password_hash because older checkout
    login only asked for email/phone. On their first password login, the
    submitted password becomes their account password.
    """
    if customer.password_hash:
        return verify_password(password, customer.password_hash), False

    customer.password_hash = hash_password(password)
    db.commit()
    db.refresh(customer)
    return True, True


class CheckPhoneIn(BaseModel):
    phone: str = Field(..., min_length=8, description="Customer phone number")


class CheckPhoneOut(BaseModel):
    exists: bool
    customer_id: str | None = None
    name: str | None = None


class LoginIn(BaseModel):
    phone: str = Field(..., min_length=8)
    password: str = Field(..., min_length=8)


class LoginOut(BaseModel):
    customer: CustomerOut
    is_new: bool = False


class GoogleLoginIn(BaseModel):
    credential: str = Field(..., description="Google ID token from GSI")


class EmailLoginIn(BaseModel):
    email: str = Field(..., min_length=5, description="Customer email or phone")
    password: str = Field(..., min_length=8, description="Customer password")


class RegisterIn(BaseModel):
    name: str = Field(..., min_length=2)
    email: str = Field(..., min_length=5)
    password: str = Field(..., min_length=8)
    phone: str = Field(..., min_length=8)
    street: str | None = Field(default=None, min_length=3)
    number: str | None = Field(default=None, min_length=1)
    complement: str | None = None
    neighborhood: str | None = Field(default=None, min_length=2)
    city: str | None = Field(default=None, min_length=2)
    state: str | None = None
    zip_code: str | None = Field(default=None, min_length=8)
    label: str | None = None
    lgpd_consent: bool = Field(..., description="Must be True to complete registration")
    lgpd_policy_version: str | None = None
    marketing_email_consent: bool = False
    marketing_whatsapp_consent: bool = False


@router.post("/check-phone")
def check_phone(body: CheckPhoneIn, db: Session = Depends(get_db)):
    customer = _find_by_phone(body.phone, db)
    if customer:
        return ok(CheckPhoneOut(exists=True, customer_id=customer.id, name=customer.name))
    return ok(CheckPhoneOut(exists=False))


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    """Authenticate a customer account by phone number + password."""
    customer = _find_by_phone(body.phone, db)
    if not customer:
        return err_msg(
            "Telefone nao encontrado. Crie sua conta primeiro.",
            code="PhoneNotFound",
            status_code=404,
        )

    authenticated, created_password = _verify_or_activate_password(customer, body.password, db)
    if not authenticated:
        return err_msg("Telefone ou senha invalidos.", code="InvalidCredentials", status_code=401)

    message = "Senha cadastrada com sucesso. Bem-vindo!" if created_password else f"Bem-vindo de volta, {customer.name}!"
    return ok(LoginOut(customer=CustomerOut.model_validate(customer), is_new=False), message)


@router.post("/login-email")
def login_email(body: EmailLoginIn, db: Session = Depends(get_db)):
    """Login by email or phone + password for registered customers."""
    identifier = body.email.strip()
    if "@" in identifier:
        customer = db.query(Customer).filter(Customer.email == identifier.lower()).first()
        if not customer:
            return err_msg(
                "E-mail nao encontrado. Crie sua conta primeiro.",
                code="EmailNotFound",
                status_code=404,
            )
    else:
        customer = _find_by_phone(identifier, db)
        if not customer:
            return err_msg(
                "Telefone nao encontrado. Crie sua conta primeiro.",
                code="PhoneNotFound",
                status_code=404,
            )

    authenticated, created_password = _verify_or_activate_password(customer, body.password, db)
    if not authenticated:
        return err_msg("E-mail/telefone ou senha invalidos.", code="InvalidCredentials", status_code=401)

    message = "Senha cadastrada com sucesso. Bem-vindo!" if created_password else f"Bem-vindo de volta, {customer.name}!"
    return ok(LoginOut(customer=CustomerOut.model_validate(customer), is_new=False), message)


@router.post("/register")
def register(body: RegisterIn, db: Session = Depends(get_db)):
    """Simple registration: name, email, password, phone and LGPD consent."""
    if not body.lgpd_consent:
        return err_msg(
            "E necessario aceitar os Termos de Privacidade para criar a conta.",
            code="LgpdRequired",
            status_code=422,
        )

    email = body.email.strip().lower()
    phone = _normalize_phone(body.phone)

    if db.query(Customer).filter(Customer.email == email).first():
        return err_msg(
            "E-mail ja cadastrado. Tente fazer login.",
            code="EmailTaken",
            status_code=409,
        )
    if phone and db.query(Customer).filter(Customer.phone == phone).first():
        return err_msg(
            "Telefone ja cadastrado. Tente fazer login.",
            code="PhoneTaken",
            status_code=409,
        )

    from datetime import datetime, timezone as tz

    now = datetime.now(tz.utc)
    new_customer = Customer(
        id=str(uuid.uuid4()),
        name=body.name.strip(),
        email=email,
        password_hash=hash_password(body.password),
        phone=phone,
        lgpd_consent=True,
        lgpd_consent_at=now,
        lgpd_policy_version=body.lgpd_policy_version,
        marketing_email_consent=body.marketing_email_consent,
        marketing_whatsapp_consent=body.marketing_whatsapp_consent,
    )
    db.add(new_customer)
    db.flush()

    if body.street and body.city:
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
    try:
        url = f"https://oauth2.googleapis.com/tokeninfo?id_token={body.credential}"
        with urllib.request.urlopen(url, timeout=10) as resp:
            payload = json.loads(resp.read())
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=401, detail="Token Google invalido ou expirado.") from exc

    google_sub = payload.get("sub")
    email = payload.get("email")
    name = payload.get("name") or payload.get("given_name") or "Cliente"

    if not google_sub or not email:
        raise HTTPException(status_code=401, detail="Token Google nao contem dados suficientes.")

    customer = (
        db.query(Customer).filter(Customer.google_id == google_sub).first()
        or db.query(Customer).filter(Customer.email == email).first()
    )

    if customer:
        if not customer.google_id:
            customer.google_id = google_sub
            db.commit()
            db.refresh(customer)
        return ok(
            LoginOut(customer=CustomerOut.model_validate(customer), is_new=False),
            f"Bem-vindo de volta, {customer.name}!",
        )

    new_customer = Customer(
        id=str(uuid.uuid4()),
        name=name,
        email=email,
        google_id=google_sub,
    )
    db.add(new_customer)
    db.commit()
    db.refresh(new_customer)

    return created(
        LoginOut(customer=CustomerOut.model_validate(new_customer), is_new=True),
        f"Bem-vindo, {new_customer.name}!",
    )
