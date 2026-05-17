from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.routes.admin_auth import get_current_admin
from backend.schemas.promotion_landing_page import (
    PromotionLandingDecisionOut,
    PromotionLandingPageCreate,
    PromotionLandingPageOut,
    PromotionLandingPageUpdate,
)
from backend.services.promotion_landing_service import PromotionLandingService

router = APIRouter(prefix="/promotion-landings", tags=["promotion-landings"])


def _landing_payload(service: PromotionLandingService, landing) -> dict:
    return {
        **PromotionLandingPageOut.model_validate(landing).model_dump(exclude={"public_url", "product_name", "promotion_name", "promotion_active_now"}),
        "public_url": f"/promocao/{landing.slug}",
        "product_name": landing.product.name if landing.product else None,
        "promotion_name": landing.promotion.name if landing.promotion else None,
        "promotion_active_now": service.promotion_is_active_now(landing.promotion),
    }


@router.get("", response_model=list[PromotionLandingPageOut])
def list_landing_pages(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    service = PromotionLandingService(db)
    return [_landing_payload(service, landing) for landing in service.list()]


@router.post("", response_model=PromotionLandingPageOut, status_code=201)
def create_landing_page(
    body: PromotionLandingPageCreate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    service = PromotionLandingService(db)
    landing = service.create(body.model_dump())
    return _landing_payload(service, landing)


@router.get("/by-product/{product_id}/promotion/{promotion_id}", response_model=PromotionLandingPageOut | None)
def get_landing_by_product_promotion(
    product_id: str,
    promotion_id: str,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    service = PromotionLandingService(db)
    landing = service.get_by_product_promotion(product_id, promotion_id)
    return _landing_payload(service, landing) if landing else None


@router.get("/slug/{slug}", response_model=PromotionLandingPageOut)
def get_public_landing(slug: str, db: Session = Depends(get_db)):
    service = PromotionLandingService(db)
    landing = service.get_public_by_slug(slug)
    return _landing_payload(service, landing)


@router.get("/decision/{product_id}", response_model=PromotionLandingDecisionOut)
def get_landing_decision(product_id: str, db: Session = Depends(get_db)):
    from backend.models.product import Product

    product = db.query(Product).filter(Product.id == product_id, Product.active == True).first()  # noqa: E712
    landing = PromotionLandingService(db).active_landing_for_product(product) if product else None
    return {
        "product_id": product_id,
        "promotion_id": landing.promotion_id if landing else None,
        "landing_page_id": landing.id if landing else None,
        "slug": landing.slug if landing else None,
        "url": f"/promocao/{landing.slug}" if landing else None,
        "should_redirect": bool(landing),
    }


@router.get("/{landing_id}", response_model=PromotionLandingPageOut)
def get_landing_page(landing_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    service = PromotionLandingService(db)
    return _landing_payload(service, service.get(landing_id))


@router.put("/{landing_id}", response_model=PromotionLandingPageOut)
def update_landing_page(
    landing_id: str,
    body: PromotionLandingPageUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    service = PromotionLandingService(db)
    landing = service.update(landing_id, body.model_dump(exclude_unset=True))
    return _landing_payload(service, landing)


@router.post("/{landing_id}/publish", response_model=PromotionLandingPageOut)
def publish_landing_page(landing_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    service = PromotionLandingService(db)
    return _landing_payload(service, service.publish(landing_id))


@router.post("/{landing_id}/unpublish", response_model=PromotionLandingPageOut)
def unpublish_landing_page(landing_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    service = PromotionLandingService(db)
    return _landing_payload(service, service.unpublish(landing_id))
