from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Index, Integer, Text
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
    __table_args__ = (
        Index("uq_payment_gateway_config_tenant_id_id", "tenant_id", "id", unique=True),
        Index("uq_payment_gateway_config_tenant_singleton", "tenant_id", unique=True),
    )

    id = Column(String, primary_key=True, default="default")
    tenant_id = Column(String, ForeignKey("tenants.id", name="fk_payment_gateway_config_tenant_id_tenants"), nullable=True)

    # Which gateway is active
    gateway = Column(String(50), default="mock")   # mock | mercadopago | stripe | pagseguro
    pix_provider = Column(String(50), nullable=False, default="mercado_pago")
    credit_card_provider = Column(String(50), nullable=False, default="mercado_pago")

    # ── Mercado Pago ──────────────────────────────────────────────────────────
    mp_enabled = Column(Boolean, default=True)
    mp_environment = Column(String(20), nullable=False, default="sandbox")
    mp_public_key = Column(String(300), nullable=True)
    mp_access_token = Column(String(300), nullable=True)
    mp_webhook_secret = Column(String(300), nullable=True)
    mp_pix_enabled = Column(Boolean, default=True)
    mp_credit_card_enabled = Column(Boolean, default=True)
    mp_max_installments = Column(Integer, default=6)
    mp_last_health_check_at = Column(DateTime(timezone=True), nullable=True)
    mp_last_health_check_status = Column(String(30), nullable=False, default="not_tested")
    mp_last_health_check_message = Column(Text, nullable=True)

    asaas_enabled = Column(Boolean, default=False)
    asaas_environment = Column(String(20), nullable=False, default="sandbox")
    asaas_api_key = Column(String(500), nullable=True)
    asaas_webhook_token = Column(String(300), nullable=True)
    asaas_pix_enabled = Column(Boolean, default=False)
    asaas_credit_card_enabled = Column(Boolean, default=False)
    asaas_max_installments = Column(Integer, default=1)
    asaas_tokenization_status = Column(String(30), nullable=False, default="not_validated")
    asaas_last_health_check_at = Column(DateTime(timezone=True), nullable=True)
    asaas_last_health_check_status = Column(String(30), nullable=False, default="not_tested")
    asaas_last_health_check_message = Column(Text, nullable=True)

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
