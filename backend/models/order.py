from sqlalchemy import Column, String, Float, Integer, Enum, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum
from backend.database import Base


class OrderStatus(str, enum.Enum):
    pending          = "pending"           # pedido criado, aguardando abertura de pagamento
    waiting_payment  = "waiting_payment"   # pagamento iniciado (PIX gerado / link aberto)
    paid             = "paid"              # pagamento confirmado pelo gateway
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
    coupon_id = Column(String, ForeignKey("coupons.id"), nullable=True)

    subtotal = Column(Float, nullable=False)
    shipping_fee = Column(Float, default=0.0)
    discount = Column(Float, default=0.0)
    total = Column(Float, nullable=False)

    estimated_time = Column(Integer, default=40)           # minutes
    loyalty_points_earned = Column(Integer, default=0)
    notes = Column(Text)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    customer = relationship("Customer", back_populates="orders")
    address = relationship("Address", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    payment = relationship("Payment", back_populates="order", uselist=False)
    coupon = relationship("Coupon", back_populates="orders")
    delivery = relationship("Delivery", back_populates="order", uselist=False)


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(String, primary_key=True)
    order_id = Column(String, ForeignKey("orders.id"), nullable=False)
    product_id = Column(String, ForeignKey("products.id"), nullable=False)

    quantity = Column(Integer, default=1)
    selected_size = Column(String(50))
    flavor_division = Column(Integer, default=1)   # 1 | 2 | 3
    unit_price = Column(Float, nullable=False)      # finalPrice per unit
    total_price = Column(Float, nullable=False)     # unit_price * quantity

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
