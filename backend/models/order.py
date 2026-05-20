from sqlalchemy import Boolean, Column, String, Float, Integer, Enum, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum
from backend.database import Base


class OrderStatus(str, enum.Enum):
    pending          = "pending"           # pedido criado, aguardando abertura de pagamento
    waiting_payment  = "waiting_payment"   # pagamento iniciado (PIX gerado / link aberto)
    paid             = "paid"              # pagamento confirmado pelo gateway
    aguardando_pagamento = "aguardando_pagamento"
    pago             = "pago"
    pagamento_recusado = "pagamento_recusado"
    pagamento_expirado = "pagamento_expirado"
    preparing        = "preparing"         # cozinha em produção
    ready_for_pickup = "ready_for_pickup"  # pronto, aguardando motoboy (opcional)
    on_the_way       = "on_the_way"        # motoboy a caminho
    delivered        = "delivered"         # entregue
    cancelled        = "cancelled"         # cancelado (terminal)
    refunded         = "refunded"          # estornado (terminal)


class Order(Base):
    __tablename__ = "orders"

    id = Column(String, primary_key=True)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=True)
    address_id = Column(String, ForeignKey("addresses.id"), nullable=True)

    # Inline delivery address (for guest checkouts)
    delivery_name = Column(String(200))
    delivery_phone = Column(String(30))
    delivery_street = Column(String(300))
    delivery_city = Column(String(100))
    delivery_complement = Column(String(100))

    status = Column(Enum(OrderStatus), default=OrderStatus.pending)
    order_code = Column(String(10), nullable=True, unique=True)
    external_reference = Column(String(120), nullable=True, unique=True)
    coupon_id = Column(String, ForeignKey("coupons.id"), nullable=True)
    campaign_id = Column(String, ForeignKey("traffic_campaigns.id", ondelete="SET NULL"), nullable=True)
    utm_source = Column(String(100), nullable=True)
    utm_medium = Column(String(100), nullable=True)
    utm_campaign = Column(String(200), nullable=True)
    utm_content = Column(String(200), nullable=True)
    utm_term = Column(String(200), nullable=True)
    session_id = Column(String(120), nullable=True)
    landing_page = Column(Text, nullable=True)
    referrer = Column(Text, nullable=True)
    sales_channel = Column(String(30), nullable=False, default="delivery")
    table_id = Column(String, ForeignKey("restaurant_tables.id", ondelete="SET NULL"), nullable=True)
    table_session_id = Column(String, ForeignKey("table_sessions.id", ondelete="SET NULL"), nullable=True)

    subtotal = Column(Float, nullable=False)
    shipping_fee = Column(Float, default=0.0)
    delivery_fee_original = Column(Float, default=0.0)
    delivery_fee_discount = Column(Float, default=0.0)
    delivery_fee_final = Column(Float, default=0.0)
    free_shipping_applied = Column(Boolean, default=False)
    discount = Column(Float, default=0.0)
    total = Column(Float, nullable=False)

    estimated_time = Column(Integer, default=40)           # minutes
    loyalty_points_earned = Column(Integer, default=0)
    notes = Column(Text)
    is_scheduled = Column(Boolean, default=False)
    scheduled_for = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    cancelled_by             = Column(String(50), nullable=True)   # "customer" | "admin" | "system"
    cancellation_reason      = Column(Text, nullable=True)
    cancelled_at             = Column(DateTime(timezone=True), nullable=True)

    paid_at                  = Column(DateTime(timezone=True), nullable=True)
    preparation_started_at   = Column(DateTime(timezone=True), nullable=True)
    out_for_delivery_at      = Column(DateTime(timezone=True), nullable=True)
    delivered_at             = Column(DateTime(timezone=True), nullable=True)
    target_delivery_minutes  = Column(Integer, default=45)
    total_time_minutes       = Column(Integer, nullable=True)
    preparation_time_minutes = Column(Integer, nullable=True)
    delivery_time_minutes    = Column(Integer, nullable=True)

    customer = relationship("Customer", back_populates="orders")
    address = relationship("Address", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    payment = relationship("Payment", back_populates="order", uselist=False)
    coupon = relationship("Coupon", back_populates="orders")
    delivery = relationship("Delivery", back_populates="order", uselist=False)
    table = relationship("RestaurantTable")
    table_session = relationship("TableSession", back_populates="orders")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(String, primary_key=True)
    order_id = Column(String, ForeignKey("orders.id"), nullable=False)
    product_id = Column(String, ForeignKey("products.id"), nullable=False)

    quantity = Column(Integer, default=1)
    selected_size = Column(String(50))
    selected_size_id = Column(String, nullable=True)
    flavor_division = Column(Integer, default=1)
    flavor_count = Column(Integer, default=1)
    selected_crust_type_id = Column(String, nullable=True)
    selected_crust_type = Column(String(100), nullable=True)
    selected_drink_variant = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    unit_price = Column(Float, nullable=False)
    total_price = Column(Float, nullable=False)
    standard_unit_price = Column(Float, nullable=True)
    applied_unit_price = Column(Float, nullable=True)
    original_price = Column(Float, nullable=True)
    is_gift = Column(Boolean, default=False)
    gift_reason = Column(String(100), nullable=True)
    coupon_id = Column(String, nullable=True)
    coupon_code = Column(String(50), nullable=True)
    promotion_id = Column(String, nullable=True)
    promotion_name = Column(String(200), nullable=True)
    promotion_discount = Column(Float, default=0.0)
    promotion_blocked = Column(Boolean, default=False)
    promotion_block_reason = Column(String(300), nullable=True)

    order = relationship("Order", back_populates="items")
    flavors = relationship("OrderItemFlavor", back_populates="order_item", cascade="all, delete-orphan")


class OrderItemFlavor(Base):
    __tablename__ = "order_item_flavors"

    id = Column(String, primary_key=True)
    order_item_id = Column(String, ForeignKey("order_items.id"), nullable=False)
    product_id = Column(String, ForeignKey("products.id"), nullable=False)
    flavor_name = Column(String(200), nullable=False)
    flavor_price = Column(Float, nullable=False)
    position = Column(Integer, default=0)          # 0-indexed slot position

    order_item = relationship("OrderItem", back_populates="flavors")
    product = relationship("Product", back_populates="order_item_flavors")
