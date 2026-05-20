from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, String, Text

from backend.database import Base


class SalaoPageSettings(Base):
    __tablename__ = "salao_page_settings"

    id = Column(String, primary_key=True, default="default")
    enabled = Column(Boolean, nullable=False, default=True)

    hero_eyebrow = Column(String(200), nullable=False, default="Restaurante italiano em Sao Paulo")
    hero_title = Column(String(200), nullable=False, default="Moschettieri")
    hero_subtitle = Column(String(300), nullable=False, default="pizza, sala e experiencia.")
    hero_description = Column(Text, nullable=False, default="Uma pagina institucional para o salao, reservas e apresentacao premium do restaurante, separada da loja delivery e integrada ao mesmo ecossistema.")
    primary_cta_label = Column(String(120), nullable=False, default="Reservar mesa")
    secondary_cta_label = Column(String(120), nullable=False, default="Ver cardapio")
    hero_background_image = Column(Text, nullable=False, default="/salao/hero-ambience.jpg")
    hero_plate_image = Column(Text, nullable=False, default="/salao/hero-plate.png")

    experience_eyebrow = Column(String(120), nullable=False, default="A casa")
    experience_title = Column(String(300), nullable=False, default="Uma experiencia pensada para o salao.")
    experience_text = Column(Text, nullable=False, default="O canal do salao nasce separado da loja delivery: outro visual, outra navegacao e outro objetivo comercial, mantendo o mesmo ERP, CRM, BI e base operacional.")
    experience_cards_json = Column(Text, nullable=False, default="[]")

    menu_eyebrow = Column(String(120), nullable=False, default="Cardapio do salao")
    menu_title = Column(String(300), nullable=False, default="Destaques da mesa.")
    menu_items_json = Column(Text, nullable=False, default="[]")

    reservation_eyebrow = Column(String(120), nullable=False, default="Reservas")
    reservation_title = Column(String(300), nullable=False, default="Reserve sua mesa.")
    reservation_text = Column(Text, nullable=False, default="Solicite sua reserva online. A equipe confirma disponibilidade e horario pelo canal de contato informado.")
    reservation_background_image = Column(Text, nullable=False, default="/salao/reservation.jpg")

    address = Column(String(300), nullable=False, default="Santana, Sao Paulo - SP")
    hours = Column(String(300), nullable=False, default="Funcionamento configuravel pelo modulo Pagina Salao.")
    phone = Column(String(120), nullable=False, default="Contato e WhatsApp integrados ao ecossistema.")
    whatsapp_url = Column(Text, nullable=False, default="")

    seo_title = Column(String(200), nullable=False, default="Moschettieri | Restaurante")
    seo_description = Column(Text, nullable=False, default="Restaurante Moschettieri: experiencia premium de salao, cardapio institucional e reservas online.")
    site_text_overrides_json = Column(Text, nullable=False, default="{}")
    site_image_overrides_json = Column(Text, nullable=False, default="{}")

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
