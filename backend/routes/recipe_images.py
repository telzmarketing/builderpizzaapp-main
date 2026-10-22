"""Authenticated recipe-image transport; ownership and validation live in the service."""
from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.core.rbac_authorization import AuthorizedTenantActor, require_rbac_permission
from backend.database import get_db
from backend.services.recipe_image_service import MAX_IMAGE_BYTES, RecipeImageService


router = APIRouter(prefix="/gestao/inventory/recipe-images", tags=["inventory-recipe-images"])


class RecipeImageOut(BaseModel):
    url: str


@router.post("", response_model=RecipeImageOut, status_code=201)
async def upload_recipe_image(
    file: UploadFile = File(...),
    actor: AuthorizedTenantActor = Depends(require_rbac_permission("inventory", "edit")),
    db: Session = Depends(get_db),
):
    data = await file.read(MAX_IMAGE_BYTES + 1)
    return RecipeImageService(db, actor.tenant_id, actor.user_id).create(data, file.content_type or "", file.filename)


@router.get("/{asset_id}")
def read_recipe_image(
    asset_id: str,
    actor: AuthorizedTenantActor = Depends(require_rbac_permission("inventory", "view")),
    db: Session = Depends(get_db),
):
    path = RecipeImageService(db, actor.tenant_id).image_path(asset_id)
    return FileResponse(path, media_type="image/png", headers={
        "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
        "Content-Disposition": 'inline; filename="referencia.png"',
    })
