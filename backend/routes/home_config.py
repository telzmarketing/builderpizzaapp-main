import json
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.home_config import HomeCatalogConfig
from backend.schemas.home_config import HomeCatalogConfigOut, HomeCatalogConfigUpdate
from backend.routes.admin_auth import get_current_admin

router = APIRouter(prefix="/home-config", tags=["home-config"])


def _get_or_create(db: Session) -> HomeCatalogConfig:
    config = db.query(HomeCatalogConfig).filter(HomeCatalogConfig.id == "default").first()
    if not config:
        config = HomeCatalogConfig(id="default")
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


@router.get("", response_model=HomeCatalogConfigOut)
def get_home_config(db: Session = Depends(get_db)):
    return _get_or_create(db)


@router.put("", response_model=HomeCatalogConfigOut)
def update_home_config(
    body: HomeCatalogConfigUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    config = _get_or_create(db)
    if body.mode is not None:
        config.mode = body.mode
    if body.selected_categories is not None:
        config.selected_categories = json.dumps(body.selected_categories)
    if body.selected_product_ids is not None:
        config.selected_product_ids = json.dumps(body.selected_product_ids)
    if body.show_promotions is not None:
        config.show_promotions = body.show_promotions
    db.commit()
    db.refresh(config)
    return config
