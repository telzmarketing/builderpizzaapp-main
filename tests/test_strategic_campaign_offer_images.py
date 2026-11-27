from decimal import Decimal

from backend.schemas.strategic_campaign import StrategicOfferCreate, StrategicOfferUpdate


def _payload():
    return {
        "code": "IMAGE-001",
        "title": "Oferta com imagem",
        "reference_type": "product",
        "product_id": "product-1",
        "price_original": Decimal("50.00"),
        "price_promotional": Decimal("39.90"),
        "image_desktop_url": "/uploads/tenant-1/desktop.webp",
        "image_mobile_url": "/uploads/tenant-1/mobile.webp",
    }


def test_offer_create_keeps_both_uploaded_image_paths():
    offer = StrategicOfferCreate(**_payload())

    assert offer.image_desktop_url == "/uploads/tenant-1/desktop.webp"
    assert offer.image_mobile_url == "/uploads/tenant-1/mobile.webp"
    assert offer.model_dump(exclude_unset=True)["image_desktop_url"].endswith("desktop.webp")
    assert offer.model_dump(exclude_unset=True)["image_mobile_url"].endswith("mobile.webp")


def test_offer_update_keeps_image_paths_for_partial_save():
    update = StrategicOfferUpdate(
        image_desktop_url="/uploads/tenant-1/desktop-new.webp",
        image_mobile_url="/uploads/tenant-1/mobile-new.webp",
    )

    assert update.model_dump(exclude_unset=True) == {
        "image_desktop_url": "/uploads/tenant-1/desktop-new.webp",
        "image_mobile_url": "/uploads/tenant-1/mobile-new.webp",
    }
