"""Add salao public page settings.

Revision ID: 20260520_salao_page_settings
Revises: 20260520_salao_reservas_foundation
Create Date: 2026-05-20
"""

from alembic import op


revision = "20260520_salao_page_settings"
down_revision = "20260520_salao_reservas_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS salao_page_settings (
            id VARCHAR PRIMARY KEY DEFAULT 'default',
            enabled BOOLEAN NOT NULL DEFAULT TRUE,
            hero_eyebrow VARCHAR(200) NOT NULL DEFAULT 'Restaurante italiano em Sao Paulo',
            hero_title VARCHAR(200) NOT NULL DEFAULT 'Moschettieri',
            hero_subtitle VARCHAR(300) NOT NULL DEFAULT 'pizza, sala e experiencia.',
            hero_description TEXT NOT NULL DEFAULT 'Uma pagina institucional para o salao, reservas e apresentacao premium do restaurante, separada da loja delivery e integrada ao mesmo ecossistema.',
            primary_cta_label VARCHAR(120) NOT NULL DEFAULT 'Reservar mesa',
            secondary_cta_label VARCHAR(120) NOT NULL DEFAULT 'Ver cardapio',
            hero_background_image TEXT NOT NULL DEFAULT '/salao/hero-ambience.jpg',
            hero_plate_image TEXT NOT NULL DEFAULT '/salao/hero-plate.png',
            experience_eyebrow VARCHAR(120) NOT NULL DEFAULT 'A casa',
            experience_title VARCHAR(300) NOT NULL DEFAULT 'Uma experiencia pensada para o salao.',
            experience_text TEXT NOT NULL DEFAULT 'O canal do salao nasce separado da loja delivery: outro visual, outra navegacao e outro objetivo comercial, mantendo o mesmo ERP, CRM, BI e base operacional.',
            experience_cards_json TEXT NOT NULL DEFAULT '[]',
            menu_eyebrow VARCHAR(120) NOT NULL DEFAULT 'Cardapio do salao',
            menu_title VARCHAR(300) NOT NULL DEFAULT 'Destaques da mesa.',
            menu_items_json TEXT NOT NULL DEFAULT '[]',
            reservation_eyebrow VARCHAR(120) NOT NULL DEFAULT 'Reservas',
            reservation_title VARCHAR(300) NOT NULL DEFAULT 'Reserve sua mesa.',
            reservation_text TEXT NOT NULL DEFAULT 'Solicite sua reserva online. A equipe confirma disponibilidade e horario pelo canal de contato informado.',
            reservation_background_image TEXT NOT NULL DEFAULT '/salao/reservation.jpg',
            address VARCHAR(300) NOT NULL DEFAULT 'Santana, Sao Paulo - SP',
            hours VARCHAR(300) NOT NULL DEFAULT 'Funcionamento configuravel pelo modulo Pagina Salao.',
            phone VARCHAR(120) NOT NULL DEFAULT 'Contato e WhatsApp integrados ao ecossistema.',
            whatsapp_url TEXT NOT NULL DEFAULT '',
            seo_title VARCHAR(200) NOT NULL DEFAULT 'Moschettieri | Restaurante',
            seo_description TEXT NOT NULL DEFAULT 'Restaurante Moschettieri: experiencia premium de salao, cardapio institucional e reservas online.',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("INSERT INTO salao_page_settings (id) VALUES ('default') ON CONFLICT DO NOTHING")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS salao_page_settings")
