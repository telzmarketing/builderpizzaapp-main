"""Versioned inventory recipes and narrowly projected public ingredient names."""
from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.core.rbac_authorization import AuthorizedTenantActor, require_rbac_permission
from backend.core.response import err
from backend.core.tenant_runtime import resolve_public_tenant_context
from backend.database import get_db
from backend.schemas.recipe_composition import (
    RecipePublishIn, RecipeArchiveIn, RecipePageOut, RecipeV1Out,
    CompositionPreviewIn, CompositionOut, PublicRecipeIngredientsOut,
)
from backend.services.recipe_composition_service import RecipeCompositionService

router = APIRouter(prefix="/gestao/inventory/v1", tags=["inventory-recipes"])
public_router = APIRouter(prefix="/products", tags=["public-ingredients"])


def service(db, actor):
    return RecipeCompositionService(db, actor.tenant_id, actor.user_id, actor.tenant_context)


def invoke(fn, *args):
    try:
        return fn(*args)
    except DomainError as exc:
        return err(exc)


@router.get("/products/{product_id}/recipes", response_model=RecipePageOut)
def list_recipes(product_id: str, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("inventory", "view"))):
    return invoke(service(db, actor).list_recipes, product_id)


@router.post("/products/{product_id}/recipes", response_model=RecipeV1Out, status_code=201)
def create_recipe(product_id: str, body: RecipePublishIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("inventory", "create")), key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200)):
    return invoke(service(db, actor).publish, product_id, body, key)


@router.put("/products/{product_id}/recipes/{recipe_id}", response_model=RecipeV1Out)
def update_recipe(product_id: str, recipe_id: str, body: RecipePublishIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("inventory", "edit")), key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200)):
    return invoke(service(db, actor).publish, product_id, body, key, recipe_id)


@router.post("/products/{product_id}/recipes/{recipe_id}/archive", response_model=RecipeV1Out)
def archive_recipe(product_id: str, recipe_id: str, body: RecipeArchiveIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("inventory", "manage")), key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200)):
    return invoke(service(db, actor).archive, product_id, recipe_id, body, key)


@router.post("/composition/preview", response_model=CompositionOut)
def preview(body: CompositionPreviewIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("inventory", "view"))):
    return invoke(service(db, actor).preview, body)


@public_router.get("/{product_id}/recipe-ingredients", response_model=PublicRecipeIngredientsOut)
def public_ingredients(product_id: str, request: Request, db: Session = Depends(get_db)):
    from backend.services.inventory_foundation_service import FoundationNotFound
    context = resolve_public_tenant_context(request, db)
    if context is None:
        return err(FoundationNotFound("Produto nao encontrado."))
    return invoke(RecipeCompositionService(db, context.tenant_id, "public:ingredients", context).public_ingredients, product_id)
