"""
Seeds the database with initial data if tables are empty.
Run once on startup.
"""
from __future__ import annotations

import uuid
from sqlalchemy.orm import Session

from backend.models.product import Product, MultiFlavorsConfig, PricingRule
from backend.models.loyalty import LoyaltyLevel, LoyaltyReward, LoyaltyRule, LoyaltyBenefit, BenefitType
from backend.models.coupon import Coupon, CouponType
from backend.models.promotion import Promotion
from backend.models.shipping import ShippingRule, ShippingRuleType
from backend.models.admin import AdminUser
from backend.models.chatbot import ChatbotSettings
from backend.models.rbac import Role, RbacModule, RbacPermission, RolePermission


def seed_all(db: Session) -> None:
    _seed_multi_flavor_config(db)
    _seed_products(db)
    _seed_promotions(db)
    _seed_loyalty(db)
    _seed_coupons(db)
    _seed_shipping(db)
    _seed_admin(db)
    _seed_chatbot_settings(db)
    _seed_rbac(db)
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

    # Tiers: Bronze 150pts, Prata 300pts, Ouro 500pts, Diamante 1000pts
    level_data = [
        ("bronze",   "Bronze",   150,  300,  "🥉", "orange"),
        ("prata",    "Prata",    300,  500,  "🥈", "gray"),
        ("ouro",     "Ouro",     500,  1000, "🥇", "yellow"),
        ("diamante", "Diamante", 1000, None, "💎", "blue"),
    ]
    level_ids = {}
    for lid, name, mn, mx, icon, color in level_data:
        level_ids[lid] = lid
        db.add(LoyaltyLevel(id=lid, name=name, min_points=mn, max_points=mx, icon=icon, color=color))

    db.flush()

    # Benefits per level
    benefits = [
        # Bronze
        (level_ids["bronze"], BenefitType.discount,     "5% de desconto",          "5% em qualquer pedido",                5.0,  0.0,  None, 1, False),
        (level_ids["bronze"], BenefitType.frete_gratis, "Entrega grátis",           "Frete grátis 1x por ciclo",            0.0,  40.0, None, 1, False),
        # Prata
        (level_ids["prata"],  BenefitType.discount,     "10% de desconto",         "10% em pedidos acima de R$30",         10.0, 30.0, None, 2, False),
        (level_ids["prata"],  BenefitType.frete_gratis, "Entrega grátis",           "Frete grátis 2x por ciclo",            0.0,  0.0,  None, 2, False),
        (level_ids["prata"],  BenefitType.product,      "Bebida grátis",            "Refrigerante 600ml grátis",            8.0,  50.0, None, 1, False),
        # Ouro
        (level_ids["ouro"],   BenefitType.discount,     "15% de desconto",         "15% em qualquer pedido",               15.0, 0.0,  None, 3, False),
        (level_ids["ouro"],   BenefitType.frete_gratis, "Entrega grátis ilimitada","Frete grátis em todos os pedidos",      0.0,  0.0,  None, 99, True),
        (level_ids["ouro"],   BenefitType.product,      "Sobremesa grátis",        "Brownie ou petit gateau por ciclo",    12.0, 60.0, None, 1, False),
        # Diamante
        (level_ids["diamante"], BenefitType.discount,   "20% de desconto VIP",    "20% em qualquer pedido",               20.0, 0.0,  None, 5, False),
        (level_ids["diamante"], BenefitType.frete_gratis,"Frete grátis VIP",       "Frete grátis ilimitado",               0.0,  0.0,  None, 99, True),
        (level_ids["diamante"], BenefitType.product,    "Pizza grátis",            "Pizza média grátis 1x por ciclo",      45.0, 80.0, None, 1, False),
        (level_ids["diamante"], BenefitType.experience, "Visita à cozinha",        "Experiência exclusiva na cozinha",      0.0,  0.0,  None, 1, False),
    ]
    for level_id, btype, label, desc, value, min_order, expires, usage_limit, stackable in benefits:
        db.add(LoyaltyBenefit(
            id=str(uuid.uuid4()),
            level_id=level_id,
            benefit_type=btype,
            label=label,
            description=desc,
            value=value,
            min_order_value=min_order,
            expires_in_days=expires,
            usage_limit=usage_limit,
            stackable=stackable,
            active=True,
        ))

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


# ── RBAC seed ─────────────────────────────────────────────────────────────────

_ROLES = [
    ("master",         "Master — acesso total ao sistema",                           True),
    ("administrador",  "Administrador — acesso quase total exceto configurações críticas", True),
    ("gerente",        "Gerente — acesso operacional e relatórios",                   True),
    ("atendente",      "Atendente — pedidos, clientes e atendimento",                 True),
    ("cozinha",        "Cozinha — visualização e produção de pedidos",                True),
    ("entregador",     "Entregador/Motoboy — acesso apenas às entregas atribuídas",   True),
    ("financeiro",     "Financeiro — caixa, pagamentos e relatórios financeiros",     True),
    ("marketing",      "Marketing — campanhas, cupons, CRM e métricas",               True),
]

_MODULES = [
    ("dashboard",       "Dashboard",              0),
    ("pedidos",         "Pedidos",                1),
    ("cardapio",        "Cardápio / Produtos",    2),
    ("categorias",      "Categorias",             3),
    ("promocoes",       "Promoções e Banners",    4),
    ("cupons",          "Cupons de Desconto",     5),
    ("kits",            "Kits e Combos",          6),
    ("clientes",        "Clientes / CRM",         7),
    ("whatsapp",        "WhatsApp / Disparador",  8),
    ("marketing",       "Marketing",              9),
    ("campanhas",       "Campanhas",              10),
    ("relatorios",      "Relatórios",             11),
    ("financeiro",      "Financeiro",             12),
    ("fluxo_caixa",     "Fluxo de Caixa",         13),
    ("formas_pagamento","Formas de Pagamento",    14),
    ("entregas",        "Entregas",               15),
    ("motoboys",        "Motoboys",               16),
    ("reservas",        "Reservas",               17),
    ("mesas",           "Mesas",                  18),
    ("loja_online",     "Loja Online",            19),
    ("funcionamento",   "Funcionamento da Loja",  20),
    ("frete",           "Frete e Regiões",        21),
    ("integracoes",     "Integrações",            22),
    ("configuracoes",   "Configurações Gerais",   23),
    ("usuarios",        "Usuários e Permissões",  24),
    ("auditoria",       "Auditoria / Logs",       25),
    ("cozinha",         "Cozinha (KDS)",          26),
]

_PERMISSIONS = [
    ("view",    "Visualizar"),
    ("create",  "Criar"),
    ("edit",    "Editar"),
    ("delete",  "Excluir"),
    ("approve", "Aprovar"),
    ("export",  "Exportar"),
    ("manage",  "Gerenciar Configurações"),
]

ALL_PERMS = ["view", "create", "edit", "delete", "approve", "export", "manage"]

# {role_name: {module_key: [perm_keys]}}
_ROLE_PERMISSIONS: dict = {
    "master": {m: ALL_PERMS for m, _, _ in _MODULES},
    "administrador": {
        "dashboard":        ["view", "export"],
        "pedidos":          ["view", "create", "edit", "delete", "approve", "export"],
        "cardapio":         ["view", "create", "edit", "delete"],
        "categorias":       ["view", "create", "edit", "delete"],
        "promocoes":        ["view", "create", "edit", "delete"],
        "cupons":           ["view", "create", "edit", "delete"],
        "kits":             ["view", "create", "edit", "delete"],
        "clientes":         ["view", "create", "edit", "delete", "export"],
        "whatsapp":         ["view", "create", "edit", "delete"],
        "marketing":        ["view", "create", "edit", "delete"],
        "campanhas":        ["view", "create", "edit", "delete"],
        "relatorios":       ["view", "export"],
        "financeiro":       ["view", "export"],
        "fluxo_caixa":      ["view", "export"],
        "formas_pagamento": ["view", "edit"],
        "entregas":         ["view", "create", "edit", "delete"],
        "motoboys":         ["view", "create", "edit", "delete"],
        "reservas":         ["view", "create", "edit", "delete"],
        "mesas":            ["view", "create", "edit", "delete"],
        "loja_online":      ["view", "edit"],
        "funcionamento":    ["view", "edit"],
        "frete":            ["view", "edit"],
        "integracoes":      ["view", "manage"],
        "configuracoes":    ["view"],
        "usuarios":         ["view", "create", "edit"],
        "auditoria":        ["view"],
        "cozinha":          ["view", "edit"],
    },
    "gerente": {
        "dashboard":     ["view"],
        "pedidos":       ["view", "create", "edit"],
        "cardapio":      ["view", "create", "edit"],
        "categorias":    ["view", "create", "edit"],
        "promocoes":     ["view", "create", "edit"],
        "cupons":        ["view", "create", "edit"],
        "clientes":      ["view", "create", "edit"],
        "relatorios":    ["view", "export"],
        "financeiro":    ["view"],
        "entregas":      ["view", "create", "edit"],
        "motoboys":      ["view", "edit"],
        "reservas":      ["view", "create", "edit"],
        "mesas":         ["view", "create", "edit"],
        "funcionamento": ["view", "edit"],
        "frete":         ["view"],
        "cozinha":       ["view", "edit"],
    },
    "atendente": {
        "dashboard":  ["view"],
        "pedidos":    ["view", "create", "edit"],
        "clientes":   ["view", "create", "edit"],
        "entregas":   ["view"],
        "cozinha":    ["view"],
    },
    "cozinha": {
        "pedidos": ["view", "edit"],
        "cozinha": ["view", "edit"],
    },
    "entregador": {
        "entregas": ["view", "edit"],
        "motoboys": ["view"],
    },
    "financeiro": {
        "dashboard":        ["view"],
        "pedidos":          ["view", "export"],
        "financeiro":       ["view", "export", "manage"],
        "fluxo_caixa":      ["view", "export"],
        "formas_pagamento": ["view", "manage"],
        "relatorios":       ["view", "export"],
    },
    "marketing": {
        "dashboard":   ["view"],
        "marketing":   ["view", "create", "edit", "delete"],
        "campanhas":   ["view", "create", "edit", "delete"],
        "cupons":      ["view", "create", "edit", "delete"],
        "clientes":    ["view", "create", "edit"],
        "whatsapp":    ["view", "create", "edit"],
        "relatorios":  ["view"],
    },
}


def _seed_rbac(db: Session) -> None:
    if db.query(Role).first():
        return  # already seeded

    # Roles
    role_map: dict[str, str] = {}  # name → id
    for name, description, is_system in _ROLES:
        r = Role(id=str(uuid.uuid4()), name=name, description=description, is_system=is_system)
        db.add(r)
        role_map[name] = r.id
    db.flush()

    # Modules
    module_map: dict[str, str] = {}  # key → id
    for key, name, order in _MODULES:
        m = RbacModule(id=str(uuid.uuid4()), key=key, name=name, order_index=order, is_active=True)
        db.add(m)
        module_map[key] = m.id
    db.flush()

    # Permissions
    perm_map: dict[str, str] = {}  # key → id
    for key, name in _PERMISSIONS:
        p = RbacPermission(id=str(uuid.uuid4()), key=key, name=name)
        db.add(p)
        perm_map[key] = p.id
    db.flush()

    # Role permissions
    for role_name, modules in _ROLE_PERMISSIONS.items():
        role_id = role_map.get(role_name)
        if not role_id:
            continue
        for mod_key, perms in modules.items():
            mod_id = module_map.get(mod_key)
            if not mod_id:
                continue
            for perm_key in perms:
                perm_id = perm_map.get(perm_key)
                if not perm_id:
                    continue
                db.add(RolePermission(
                    id=str(uuid.uuid4()),
                    role_id=role_id,
                    module_id=mod_id,
                    permission_id=perm_id,
                    allowed=True,
                ))
    db.flush()
