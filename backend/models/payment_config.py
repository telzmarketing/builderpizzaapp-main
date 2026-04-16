from sqlalchemy import Column, String, Boolean, DateTime, Text
from datetime import datetime, timezone
from backend.database import Base


class PaymentGatewayConfig(Base):
    """
    Stores payment gateway settings editable via the admin panel.
    Only one row is active at a time (id='default').

    Secret keys are stored as-is here (no encryption at rest).
    In production, use a secrets manager (AWS Secrets Manager, Vault, etc.)
    or encrypt the column with SQLAlchemy-Utils EncryptedType.
    """
    __tablename__ = "payment_gateway_config"

    id = Column(String, primary_key=True, default="default")

    # Which gateway is active
    gateway = Column(String(50), default="mock")   # mock | mercadopago | stripe | pagseguro

    # ── Mercado Pago ──────────────────────────────────────────────────────────
    mp_public_key = Column(String(300), nullable=True)
    mp_access_token = Column(String(300), nullable=True)
    mp_webhook_secret = Column(String(300), nullable=True)

    # ── Stripe ────────────────────────────────────────────────────────────────
    stripe_publishable_key = Column(String(300), nullable=True)
    stripe_secret_key = Column(String(300), nullable=True)
    stripe_webhook_secret = Column(String(300), nullable=True)

    # ── PagSeguro ─────────────────────────────────────────────────────────────
    pagseguro_email = Column(String(200), nullable=True)
    pagseguro_token = Column(String(300), nullable=True)

    # ── PIX (chave avulsa, sem gateway específico) ───────────────────────────
    pix_key = Column(String(200), nullable=True)          # CPF, CNPJ, email, telefone ou aleatória
    pix_key_type = Column(String(30), nullable=True)      # cpf | cnpj | email | phone | random
    pix_beneficiary_name = Column(String(200), nullable=True)
    pix_beneficiary_city = Column(String(100), nullable=True)

    # ── Métodos aceitos ───────────────────────────────────────────────────────
    accept_pix = Column(Boolean, default=True)
    accept_credit_card = Column(Boolean, default=True)
    accept_debit_card = Column(Boolean, default=False)
    accept_cash = Column(Boolean, default=True)

    # ── Ambiente ─────────────────────────────────────────────────────────────
    sandbox = Column(Boolean, default=True)               # True = teste, False = produção

    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
