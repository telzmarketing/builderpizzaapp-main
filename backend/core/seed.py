"""
Seeds the database with initial data if tables are empty.
Run once on startup.
"""
import uuid
from sqlalchemy.orm import Session

from backend.models.product import Product, MultiFlavorsConfig, PricingRule
from backend.models.loyalty import LoyaltyLevel, LoyaltyReward, LoyaltyRule
from backend.models.coupon import Coupon, CouponType
from backend.models.promotion import Promotion
from backend.models.shipping import ShippingRule, ShippingRuleType
from backend.models.admin import AdminUser
from backend.models.chatbot import ChatbotSettings


def seed_all(db: Session) -> None:
    _seed_multi_flavor_config(db)
    _seed_products(db)
    _seed_promotions(db)
    _seed_loyalty(db)
    _seed_coupons(db)
    _seed_shipping(db)
    _seed_admin(db)
    _seed_chatbot_settings(db)
    db.commit()


def _seed_admin(db: Session) -> None:
    if db.query(AdminUser).first():
        return
    import os
    from backend.core.security import hash_password

    email = os.getenv("ADMIN_EMAIL", "admin@minhaloja.com.br")
    password = os.getenv("ADMIN_PASSWORD", "")
    name = os.getenv("ADMIN_NAME", "Administrador")

    if not password:
        raise RuntimeError(
            "ADMIN_PASSWORD não definida no ambiente. "
            "Adicione ADMIN_PASSWORD=SuaSenhaForte no backend/.env antes de iniciar."
        )

    db.add(AdminUser(
        id=str(uuid.uuid4()),
        email=email,
        name=name,
        password_hash=hash_password(password),
    ))


def _seed_multi_flavor_config(db: Session) -> None:
    if db.query(MultiFlavorsConfig).filter(MultiFlavorsConfig.id == "default").first():
        return
    db.add(MultiFlavorsConfig(id="default", max_flavors=2, pricing_rule=PricingRule.most_expensive))


def _seed_products(db: Session) -> None:
    if db.query(Product).first():
        return
    products = [
        ("Calabresa",    "Molho de tomate, mussarela, calabresa fatiada e orégano",  35.0, "🍕", 4.5),
        ("Frango c/ Catupiry", "Frango desfiado, catupiry e azeitonas",              42.0, "🐔", 4.7),
        ("Portuguesa",   "Presunto, ovos, cebola, pimentão e ervilhas",              38.0, "🇵🇹", 4.3),
        ("Margherita",   "Molho de tomate fresco, mussarela de búfala e manjericão", 40.0, "🌿", 4.8),
        ("Pepperoni",    "Molho especial, mussarela e pepperoni artesanal",           45.0, "🔴", 4.9),
        ("Camarão",      "Camarão salteado ao alho, molho branco e catupiry",        65.0, "🦐", 4.6),
        ("4 Queijos",    "Mussarela, parmesão, gorgonzola e provolone",              48.0, "🧀", 4.7),
        ("Vegana",       "Legumes assados, pimentão, abobrinha e molho de tomate",   37.0, "🥦", 4.4),
    ]
    for name, desc, price, icon, rating in products:
        db.add(Product(
            id=f"prod-{uuid.uuid4().hex[:8]}",
            name=name, description=desc, price=price, icon=icon, rating=rating,
        ))


def _seed_promotions(db: Session) -> None:
    if db.query(Promotion).first():
        return
    db.add(Promotion(
        id=str(uuid.uuid4()),
        title="20% off",
        subtitle="Em qualquer pizza",
        icon="🍕",
        active=True,
    ))


def _seed_loyalty(db: Session) -> None:
    if db.query(LoyaltyLevel).first():
        return
    levels = [
        ("Bronze",   0,    500,  "🥉", "orange"),
        ("Prata",    501,  1500, "🥈", "gray"),
        ("Ouro",     1501, 3000, "🥇", "yellow"),
        ("Diamante", 3001, None, "💎", "blue"),
    ]
    for name, mn, mx, icon, color in levels:
        db.add(LoyaltyLevel(id=str(uuid.uuid4()), name=name, min_points=mn, max_points=mx, icon=icon, color=color))

    rewards = [
        ("Pizza Grátis",       500,  "🍕"),
        ("Entrega Grátis",     200,  "🛵"),
        ("Desconto de R$15",   300,  "💰"),
        ("Bebida Grátis",      150,  "🥤"),
    ]
    for label, pts, icon in rewards:
        db.add(LoyaltyReward(id=str(uuid.uuid4()), label=label, points_required=pts, icon=icon))

    rules = [
        ("Primeiro Pedido",   "⭐", 50,  "first_order"),
        ("A cada R$1 gasto",  "💸", 1,   "per_real"),
        ("Pedido Entregue",   "📦", 10,  "per_order"),
    ]
    for label, icon, pts, rtype in rules:
        db.add(LoyaltyRule(id=str(uuid.uuid4()), label=label, icon=icon, points=pts, rule_type=rtype))


def _seed_coupons(db: Session) -> None:
    if db.query(Coupon).first():
        return
    db.add(Coupon(
        id=str(uuid.uuid4()),
        code="BEMVINDO10",
        description="10% de desconto na primeira compra",
        icon="🎉",
        coupon_type=CouponType.percentage,
        discount_value=10.0,
        min_order_value=30.0,
    ))
    db.add(Coupon(
        id=str(uuid.uuid4()),
        code="FRETE0",
        description="Frete grátis em qualquer pedido",
        icon="🛵",
        coupon_type=CouponType.fixed,
        discount_value=10.0,
        min_order_value=0.0,
    ))


def _seed_chatbot_settings(db: Session) -> None:
    if db.query(ChatbotSettings).filter(ChatbotSettings.id == "default").first():
        return
    db.add(ChatbotSettings(
        id="default",
        prompt_base=(
            "Você é um assistente virtual de uma pizzaria. "
            "Responda em português, seja simpático e objetivo. "
            "Ajude o cliente com dúvidas sobre cardápio, pedidos, entrega e pagamento."
        ),
    ))


def _seed_shipping(db: Session) -> None:
    if db.query(ShippingRule).first():
        return
    # Global fixed rule (lowest priority — fallback)
    db.add(ShippingRule(
        id=str(uuid.uuid4()),
        name="Taxa padrão",
        rule_type=ShippingRuleType.fixed,
        base_price=8.0,
        priority=0,
    ))
    # Free shipping above R$100
    db.add(ShippingRule(
        id=str(uuid.uuid4()),
        name="Frete grátis acima de R$100",
        rule_type=ShippingRuleType.free_above,
        base_price=8.0,
        free_above_amount=100.0,
        priority=10,
    ))
