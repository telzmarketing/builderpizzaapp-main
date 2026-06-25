from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.core.security import hash_password
from backend.models.customer import Customer
from backend.models.customer_identity import CustomerAuth, CustomerChannel, CustomerPreference

SYSTEM_LEAD_EMAIL_DOMAIN = "leads.moschettieri.com.br"
LEGACY_SYSTEM_LEAD_EMAIL_DOMAINS = {"lead.whatsapp.local"}


def normalize_phone(phone: str | None) -> str:
    if not phone:
        return ""
    return re.sub(r"\D", "", phone)


def normalize_email(email: str | None) -> str:
    return (email or "").strip().lower()


def is_system_lead_email(email: str | None) -> bool:
    normalized = normalize_email(email)
    return normalized.endswith(f"@{SYSTEM_LEAD_EMAIL_DOMAIN}") or any(
        normalized.endswith(f"@{domain}") for domain in LEGACY_SYSTEM_LEAD_EMAIL_DOMAINS
    )


def system_lead_email(phone: str) -> str:
    return f"whatsapp+{phone}@{SYSTEM_LEAD_EMAIL_DOMAIN}"


class CustomerIdentityService:
    def __init__(self, db: Session):
        self._db = db

    def find_by_phone(self, phone: str | None, *, channel: str | None = None) -> Customer | None:
        normalized = normalize_phone(phone)
        if not normalized:
            return None

        q = self._db.query(CustomerChannel).filter(CustomerChannel.normalized_identifier == normalized)
        if channel:
            q = q.filter(CustomerChannel.channel == channel)
        channel_row = q.first()
        if channel_row:
            return self._db.query(Customer).filter(Customer.id == channel_row.customer_id).first()

        return (
            self._db.query(Customer)
            .filter(or_(Customer.phone == normalized, Customer.phone == phone))
            .first()
        )

    def ensure_channel(
        self,
        customer: Customer,
        *,
        channel: str,
        identifier: str,
        source: str | None = None,
        is_primary: bool = False,
        marketing_consent: bool = False,
    ) -> CustomerChannel | None:
        normalized = normalize_phone(identifier) if channel in {"phone", "whatsapp"} else normalize_email(identifier)
        if not normalized:
            return None

        existing = (
            self._db.query(CustomerChannel)
            .filter(
                CustomerChannel.channel == channel,
                CustomerChannel.normalized_identifier == normalized,
            )
            .first()
        )
        if existing:
            if existing.customer_id == customer.id:
                existing.identifier = identifier
                existing.is_primary = existing.is_primary or is_primary
                existing.marketing_consent = existing.marketing_consent or marketing_consent
                existing.source = existing.source or source
                existing.updated_at = datetime.now(timezone.utc)
            return existing

        row = CustomerChannel(
            id=str(uuid.uuid4()),
            customer_id=customer.id,
            channel=channel,
            identifier=identifier,
            normalized_identifier=normalized,
            is_primary=is_primary,
            marketing_consent=marketing_consent,
            source=source,
        )
        self._db.add(row)
        return row

    def ensure_preferences(self, customer: Customer, *, preferred_channel: str | None = None) -> CustomerPreference:
        row = (
            self._db.query(CustomerPreference)
            .filter(CustomerPreference.customer_id == customer.id)
            .first()
        )
        if row:
            if preferred_channel and not row.preferred_channel:
                row.preferred_channel = preferred_channel
                row.updated_at = datetime.now(timezone.utc)
            return row

        row = CustomerPreference(
            id=str(uuid.uuid4()),
            customer_id=customer.id,
            preferred_channel=preferred_channel,
        )
        self._db.add(row)
        return row

    def ensure_auth(
        self,
        customer: Customer,
        *,
        auth_provider: str,
        identifier: str | None = None,
        password_hash_value: str | None = None,
        provider_subject: str | None = None,
        status: str = "active",
    ) -> CustomerAuth:
        normalized_identifier = normalize_email(identifier) if identifier else None
        row = (
            self._db.query(CustomerAuth)
            .filter(
                CustomerAuth.customer_id == customer.id,
                CustomerAuth.auth_provider == auth_provider,
            )
            .first()
        )
        if not row:
            row = CustomerAuth(
                id=str(uuid.uuid4()),
                customer_id=customer.id,
                auth_provider=auth_provider,
                identifier=normalized_identifier,
                password_hash=password_hash_value,
                provider_subject=provider_subject,
                status=status,
            )
            self._db.add(row)
            return row

        row.identifier = normalized_identifier or row.identifier
        row.password_hash = password_hash_value or row.password_hash
        row.provider_subject = provider_subject or row.provider_subject
        row.status = status or row.status
        row.updated_at = datetime.now(timezone.utc)
        return row

    def sync_registered_customer(
        self,
        customer: Customer,
        *,
        auth_provider: str = "password",
        password_hash_value: str | None = None,
        provider_subject: str | None = None,
    ) -> None:
        if customer.email:
            self.ensure_channel(
                customer,
                channel="email",
                identifier=customer.email,
                source=customer.source or "registration",
                is_primary=not bool(customer.phone),
                marketing_consent=bool(customer.marketing_email_consent),
            )
            if auth_provider in {"password", "google"}:
                self.ensure_auth(
                    customer,
                    auth_provider=auth_provider,
                    identifier=customer.email,
                    password_hash_value=password_hash_value,
                    provider_subject=provider_subject,
                    status="active",
                )

        if customer.phone:
            self.ensure_channel(
                customer,
                channel="phone",
                identifier=customer.phone,
                source=customer.source or "registration",
                is_primary=True,
                marketing_consent=bool(customer.marketing_whatsapp_consent),
            )
            self.ensure_channel(
                customer,
                channel="whatsapp",
                identifier=customer.phone,
                source=customer.source or "registration",
                is_primary=True,
                marketing_consent=bool(customer.marketing_whatsapp_consent),
            )
        self.ensure_preferences(customer, preferred_channel="whatsapp" if customer.phone else "email")

    def get_or_create_whatsapp_lead(
        self,
        *,
        phone: str,
        name: str | None = None,
        source: str = "whatsapp",
    ) -> tuple[Customer, bool]:
        normalized = normalize_phone(phone)
        if not normalized:
            raise ValueError("Telefone invalido.")

        existing = self.find_by_phone(normalized, channel="whatsapp") or self.find_by_phone(normalized)
        if existing:
            if not existing.phone:
                existing.phone = normalized
            if name and existing.name.startswith("Cliente WhatsApp"):
                existing.name = name.strip()
            existing.last_contact_at = datetime.now(timezone.utc)
            self.ensure_channel(
                existing,
                channel="whatsapp",
                identifier=normalized,
                source=source,
                is_primary=True,
                marketing_consent=bool(existing.marketing_whatsapp_consent),
            )
            self.ensure_preferences(existing, preferred_channel="whatsapp")
            return existing, False

        label = name.strip() if name and name.strip() else f"Cliente WhatsApp {normalized[-4:]}"
        customer = Customer(
            id=str(uuid.uuid4()),
            name=label,
            email=system_lead_email(normalized),
            phone=normalized,
            crm_status="lead",
            source=source,
            marketing_whatsapp_consent=False,
            last_contact_at=datetime.now(timezone.utc),
        )
        self._db.add(customer)
        self._db.flush()
        self.ensure_channel(
            customer,
            channel="whatsapp",
            identifier=normalized,
            source=source,
            is_primary=True,
            marketing_consent=False,
        )
        self.ensure_channel(
            customer,
            channel="phone",
            identifier=normalized,
            source=source,
            is_primary=True,
            marketing_consent=False,
        )
        self.ensure_auth(customer, auth_provider="none", identifier=None, status="inactive")
        self.ensure_preferences(customer, preferred_channel="whatsapp")
        return customer, True

    def complete_lead_registration(
        self,
        customer: Customer,
        *,
        name: str,
        email: str,
        password: str,
        lgpd_consent: bool,
        lgpd_policy_version: str | None,
        marketing_email_consent: bool,
        marketing_whatsapp_consent: bool,
    ) -> Customer:
        now = datetime.now(timezone.utc)
        password_hash_value = hash_password(password)
        customer.name = name.strip()
        customer.email = normalize_email(email)
        customer.password_hash = password_hash_value
        customer.lgpd_consent = lgpd_consent
        customer.lgpd_consent_at = now
        customer.lgpd_policy_version = lgpd_policy_version
        customer.marketing_email_consent = marketing_email_consent
        customer.marketing_whatsapp_consent = marketing_whatsapp_consent
        customer.crm_status = "active"
        customer.updated_at = now
        self.sync_registered_customer(
            customer,
            auth_provider="password",
            password_hash_value=password_hash_value,
        )
        return customer
