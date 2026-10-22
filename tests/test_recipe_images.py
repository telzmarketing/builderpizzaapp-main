"""Private recipe media cannot fall through public/optimized legacy serving."""
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4
import os

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.services.recipe_image_service import RecipeImageInvalid, RecipeImageService


def raster():
    output = BytesIO()
    Image.new("RGB", (4, 4), "red").save(output, format="PNG")
    return output.getvalue()


@pytest.mark.parametrize("data,kind", [(b"<script>alert(1)</script>", "image/png"), (b"anything", "image/svg+xml"), (b"", "image/jpeg")])
def test_image_rejects_non_raster_content_before_persistence(data, kind):
    with pytest.raises(RecipeImageInvalid):
        RecipeImageService(None, "tenant").create(data, kind, "test")


@pytest.mark.parametrize("path", [".recipe-private/test.png", ".recipe-private\\test.png", "tenant/.recipe-private/test.png"])
def test_private_recipe_storage_never_enters_generic_upload_or_optimization(path):
    from backend.routes.upload_optimized import _safe_upload_path, _enforce_tenant_upload_read
    for check in (lambda: _safe_upload_path(path), lambda: _enforce_tenant_upload_read(None, None, path)):
        with pytest.raises(HTTPException) as exc:
            check()
        assert exc.value.status_code == 404


@pytest.fixture
def image_database():
    url = os.environ.get("INVENTORY_FOUNDATION_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Requires explicitly configured disposable PostgreSQL")
    parsed = make_url(url)
    assert parsed.get_backend_name() == "postgresql" and parsed.host in {"localhost", "127.0.0.1", "postgres"}
    assert "test" in parsed.database or parsed.database.endswith("_ci")
    from backend.main import app  # noqa: F401 register models without lifespan
    from backend.models.tenant import Tenant
    from backend.models.admin import AdminUser
    engine = create_engine(url)
    token = uuid4().hex
    tenant, other, actor = "recipe-image-" + token, "other-image-" + token, "image-actor-" + token
    with Session(engine) as db:
        db.add_all([Tenant(id=tenant, slug=tenant, name="Synthetic recipe images"), Tenant(id=other, slug=other, name="Synthetic isolation")])
        db.add(AdminUser(id=actor, name="Image audit", email=token + "@example.invalid", password_hash="not-a-login"))
        db.commit()
    yield SimpleNamespace(engine=engine, tenant=tenant, other=other, actor=actor)
    engine.dispose()


def test_pg_recipe_image_roundtrip_auth_tenant_and_no_public_fallback(image_database, monkeypatch, tmp_path):
    from backend.database import get_db
    from backend.routes import recipe_images, upload_optimized
    case = image_database
    monkeypatch.chdir(tmp_path)
    app = FastAPI()
    app.include_router(recipe_images.router, prefix="/api")
    app.include_router(upload_optimized.router)

    @app.exception_handler(DomainError)
    async def domain_handler(request, exc):
        return JSONResponse(status_code=exc.http_status, content={"code": exc.code})

    def database():
        with Session(case.engine) as db:
            yield db

    app.dependency_overrides[get_db] = database
    with TestClient(app) as client:
        # Real dependency, no token: denied before any upload is accepted.
        denied = client.post("/api/gestao/inventory/recipe-images", files={"file": ("test.png", raster(), "image/png")})
        assert denied.status_code in {401, 403}

        actor = SimpleNamespace(tenant_id=case.tenant, user_id=case.actor)
        for route in app.routes:
            for dependency in getattr(getattr(route, "dependant", None), "dependencies", []):
                if dependency.name == "actor":
                    app.dependency_overrides[dependency.call] = lambda: actor
        response = client.post("/api/gestao/inventory/recipe-images", files={"file": ("../../test.png", raster(), "image/png")})
        assert response.status_code == 201, response.text
        url = response.json()["url"]
        asset_id = url.rsplit("/", 1)[1]
        result = client.get(url)
        assert result.status_code == 200 and result.content.startswith(b"\x89PNG")
        assert result.headers["cache-control"] == "private, no-store"
        assert client.get(f"/uploads/.recipe-private/{asset_id}.png").status_code == 404
        assert client.get(f"/uploads/optimized/640/.recipe-private/{asset_id}.png").status_code == 404
        with Session(case.engine) as db:
            assert RecipeImageService(db, case.tenant).validate_reference(url) == url
            with pytest.raises(RecipeImageInvalid):
                RecipeImageService(db, case.tenant).validate_reference("https://external.invalid/image.png")
        actor = SimpleNamespace(tenant_id=case.other, user_id=case.actor)
        assert client.get(url).status_code == 404
