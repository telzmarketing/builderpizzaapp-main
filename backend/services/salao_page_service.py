import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.models.salao_page import SalaoPageSettings


DEFAULT_EXPERIENCE_CARDS = [
    {
        "title": "Ambiente acolhedor",
        "text": "Uma casa italiana para jantar com calma, vinho na mesa e atendimento presente.",
        "image": "/salao/experience-01.jpg",
    },
    {
        "title": "Forno, massa e tradicao",
        "text": "Receitas feitas para valorizar a pizza servida no salao, com textura, aroma e tempo certo.",
        "image": "/salao/experience-02.jpg",
    },
]

DEFAULT_MENU_ITEMS = [
    {"name": "Pizza Marguerita", "description": "Disponivel para composicao do cardapio institucional do salao."},
    {"name": "Pizza Portuguesa", "description": "Disponivel para composicao do cardapio institucional do salao."},
    {"name": "Pizza Quatro Queijos", "description": "Disponivel para composicao do cardapio institucional do salao."},
    {"name": "Pizza Calabresa", "description": "Disponivel para composicao do cardapio institucional do salao."},
]


class SalaoPageService:
    def __init__(self, db: Session):
        self._db = db

    def get_or_create(self) -> SalaoPageSettings:
        settings = self._db.query(SalaoPageSettings).filter(SalaoPageSettings.id == "default").first()
        if settings:
            return settings
        settings = SalaoPageSettings(
            id="default",
            experience_cards_json=json.dumps(DEFAULT_EXPERIENCE_CARDS, ensure_ascii=False),
            menu_items_json=json.dumps(DEFAULT_MENU_ITEMS, ensure_ascii=False),
        )
        self._db.add(settings)
        self._db.commit()
        self._db.refresh(settings)
        return settings

    def update(self, payload: dict[str, Any]) -> SalaoPageSettings:
        settings = self.get_or_create()
        for key, value in payload.items():
            if key == "experience_cards":
                settings.experience_cards_json = json.dumps(value, ensure_ascii=False)
            elif key == "menu_items":
                settings.menu_items_json = json.dumps(value, ensure_ascii=False)
            elif key == "site_text_overrides":
                settings.site_text_overrides_json = json.dumps(self._clean_override_map(value), ensure_ascii=False)
            elif key == "site_image_overrides":
                settings.site_image_overrides_json = json.dumps(self._clean_override_map(value), ensure_ascii=False)
            elif hasattr(settings, key):
                setattr(settings, key, value)
        settings.updated_at = datetime.now(timezone.utc)
        self._db.commit()
        self._db.refresh(settings)
        return settings

    def serialize(self, settings: SalaoPageSettings | None = None) -> dict[str, Any]:
        item = settings or self.get_or_create()
        return {
            "id": item.id,
            "enabled": bool(item.enabled),
            "hero_eyebrow": item.hero_eyebrow,
            "hero_title": item.hero_title,
            "hero_subtitle": item.hero_subtitle,
            "hero_description": item.hero_description,
            "primary_cta_label": item.primary_cta_label,
            "secondary_cta_label": item.secondary_cta_label,
            "hero_background_image": item.hero_background_image,
            "hero_plate_image": item.hero_plate_image,
            "experience_eyebrow": item.experience_eyebrow,
            "experience_title": item.experience_title,
            "experience_text": item.experience_text,
            "experience_cards": self._json_list(item.experience_cards_json, DEFAULT_EXPERIENCE_CARDS),
            "menu_eyebrow": item.menu_eyebrow,
            "menu_title": item.menu_title,
            "menu_items": self._json_list(item.menu_items_json, DEFAULT_MENU_ITEMS),
            "reservation_eyebrow": item.reservation_eyebrow,
            "reservation_title": item.reservation_title,
            "reservation_text": item.reservation_text,
            "reservation_background_image": item.reservation_background_image,
            "address": item.address,
            "hours": item.hours,
            "phone": item.phone,
            "whatsapp_url": item.whatsapp_url,
            "seo_title": item.seo_title,
            "seo_description": item.seo_description,
            "site_text_overrides": self._json_map(item.site_text_overrides_json),
            "site_image_overrides": self._json_map(item.site_image_overrides_json),
            "created_at": item.created_at,
            "updated_at": item.updated_at,
        }

    @staticmethod
    def _json_list(raw: str | None, fallback: list[dict[str, str]]) -> list[dict[str, str]]:
        if not raw:
            return fallback
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return [item for item in data if isinstance(item, dict)]
        except Exception:
            pass
        return fallback

    @staticmethod
    def _json_map(raw: str | None) -> dict[str, str]:
        if not raw:
            return {}
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return {str(key): str(value) for key, value in data.items() if value is not None}
        except Exception:
            pass
        return {}

    @staticmethod
    def _clean_override_map(value: Any) -> dict[str, str]:
        if not isinstance(value, dict):
            return {}
        return {
            str(key): str(item)
            for key, item in value.items()
            if item is not None and str(item).strip()
        }
