"""HTTP persistence, upload and real JWT/RBAC checks for the manager identity."""
from io import BytesIO
import json
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from PIL import Image
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.config import get_settings
from backend.core import security
from backend.core.exceptions import DomainError
from backend.database import Base, get_db
from backend.models.admin import AdminUser
from backend.models.platform_rbac import PlatformRole, PlatformPermission, PlatformRolePermission, PlatformUserRole
from backend.routes.site_config import router as site_router


PATH = "/api/admin/platform/settings/branding"


def image_bytes(format="PNG"):
    output = BytesIO()
    Image.new("RGB", (24, 24), "blue").save(output, format=format)
    return output.getvalue()


@pytest.fixture
def platform_branding(monkeypatch, tmp_path):
    from backend.routes import platform_settings as routes

    for name, value in {
        "PLATFORM_RBAC_ENABLED": "true",
        "TENANT_DOMAINS_ENABLED": "false",
        "MULTI_TENANT_AUTH_ENABLED": "false",
    }.items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()
    monkeypatch.setattr(security, "settings", SimpleNamespace(
        JWT_SECRET_KEY="platform-branding-test-private-secret", JWT_ALGORITHM="HS256", JWT_EXPIRE_MINUTES=60))
    monkeypatch.chdir(tmp_path)
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[AdminUser.__table__, PlatformRole.__table__, PlatformPermission.__table__,
        PlatformRolePermission.__table__, PlatformUserRole.__table__])
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE site_config (id VARCHAR PRIMARY KEY, content TEXT NOT NULL, updated_at TIMESTAMP)")
        for key in ("default", "tenant:a:site-content", "tenant:b:site-content"):
            connection.execute(text("INSERT INTO site_config VALUES (:key, :content, CURRENT_TIMESTAMP)"),
                {"key": key, "content": json.dumps({"brand": {"name": key, "faviconUrl": "/uploads/tenant.png"}})})
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    for user in ("manager", "viewer", "tenant"):
        db.add(AdminUser(id=user, email=f"{user}@example.com", name=user, password_hash="unused",
            active=True, force_password_change=False))
    for role in ("manager", "viewer"):
        db.add(PlatformRole(id=role, key=role, name=role))
        db.add(PlatformUserRole(id=role, user_id=role, role_id=role))
    for action in ("view", "manage"):
        key = f"platform_settings.{action}"
        db.add(PlatformPermission(id=key, key=key, name=key))
        db.add(PlatformRolePermission(id=f"manager-{action}", role_id="manager", permission_id=key))
    db.add(PlatformRolePermission(id="viewer-view", role_id="viewer", permission_id="platform_settings.view"))
    db.commit()
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")
    app.include_router(routes.public_router, prefix="/api")
    app.include_router(site_router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: db

    @app.exception_handler(DomainError)
    def domain_error(request, exc):
        return JSONResponse(status_code=exc.http_status, content={"error": exc.code})

    def headers(user="manager", **claims):
        token = security.create_access_token(user, extra=claims)
        return {"Authorization": f"Bearer {token}", "host": "app.telz.com.br"}

    with TestClient(app) as client:
        yield SimpleNamespace(client=client, db=db, headers=headers, upload_dir=tmp_path)
    db.close()
    engine.dispose()
    get_settings.cache_clear()


@pytest.mark.parametrize("method", ["get", "put", "post"])
def test_real_rbac_denies_anonymous_tenant_and_support(platform_branding, method):
    env = platform_branding
    path = PATH + ("/upload" if method == "post" else "")
    kwargs = {"json": {"logo_url": "", "favicon_url": ""}} if method == "put" else (
        {"files": {"file": ("logo.png", image_bytes(), "image/png")}} if method == "post" else {})
    request = getattr(env.client, method)
    assert request(path, **kwargs).status_code == 401
    assert request(path, headers=env.headers("tenant", tenant_id="tenant-a"), **kwargs).status_code == 403
    assert request(path, headers=env.headers(token_kind="support"), **kwargs).status_code == 403


def test_view_permission_does_not_authorize_save_or_upload(platform_branding):
    env = platform_branding
    headers = env.headers("viewer")
    assert env.client.get(PATH, headers=headers).status_code == 200
    assert env.client.put(PATH, headers=headers, json={"logo_url": "", "favicon_url": ""}).status_code == 403
    assert env.client.post(PATH + "/upload", headers=headers,
        files={"file": ("logo.png", image_bytes(), "image/png")}).status_code == 403


def test_platform_branding_hidden_when_rbac_disabled(platform_branding, monkeypatch):
    monkeypatch.setenv("PLATFORM_RBAC_ENABLED", "false")
    get_settings.cache_clear()
    env = platform_branding
    assert env.client.get(PATH, headers=env.headers()).status_code == 404
    assert env.client.put(PATH, headers=env.headers(), json={"logo_url": "", "favicon_url": ""}).status_code == 404


def upload(env, format="PNG"):
    response = env.client.post(PATH + "/upload", headers=env.headers(),
        files={"file": ("brand." + format.lower(), image_bytes(format), "image/" + format.lower())})
    assert response.status_code == 200, response.text
    return response.json()["data"]["url"]


def test_save_public_projection_isolation_and_reset(platform_branding):
    env = platform_branding
    original = list(env.db.execute(text("SELECT id, content FROM site_config ORDER BY id")))
    logo, favicon = upload(env), upload(env, "WEBP")
    payload = {"logo_url": logo, "favicon_url": favicon}
    saved = env.client.put(PATH, headers=env.headers(), json=payload)
    assert saved.status_code == 200, saved.text
    assert saved.json()["data"] == payload
    assert env.client.get(PATH, headers=env.headers()).json()["data"] == payload
    persisted = json.loads(env.db.execute(text("SELECT content FROM site_config WHERE id='platform:branding'")).scalar_one())
    assert persisted == payload
    assert list(env.db.execute(text("SELECT id, content FROM site_config WHERE id != 'platform:branding' ORDER BY id"))) == original
    public = env.client.get("/api/site-config", headers={"host": "app.telz.com.br"}).json()["data"]
    assert public == {"brand": {"name": "Telz", "pageTitle": "Telz", "logo": logo, "faviconUrl": favicon}}
    redirect = env.client.get("/api/site-config/favicon?size=32", headers={"host": "app.telz.com.br"}, follow_redirects=False)
    assert redirect.status_code == 307
    assert redirect.headers["location"].startswith(favicon + "?v=")
    assert "no-store" in redirect.headers["cache-control"]
    reset = env.client.put(PATH, headers=env.headers(), json={"logo_url": "", "favicon_url": ""})
    assert reset.status_code == 200
    redirect = env.client.get("/api/site-config/favicon", headers={"host": "app.telz.com.br"}, follow_redirects=False)
    assert redirect.headers["location"].startswith("/icons/telz.svg")


@pytest.mark.parametrize("enabled", [False, True])
def test_public_asset_is_available_independent_of_tenant_namespace(platform_branding, monkeypatch, enabled):
    env = platform_branding
    monkeypatch.setenv("TENANT_UPLOAD_NAMESPACE_ENABLED", str(enabled).lower())
    get_settings.cache_clear()
    url = upload(env, "JPEG")
    result = env.client.get(url)
    assert result.status_code == 200
    assert result.headers["content-type"].startswith("image/png")
    with Image.open(BytesIO(result.content)) as image:
        assert image.format == "PNG"
        assert image.size == (24, 24)
    assert env.client.get(url.replace(".png", ".svg")).status_code == 404
    assert env.client.get("/api/platform/branding/assets/not-a-uuid.png").status_code == 404


@pytest.mark.parametrize("content,mime", [
    (b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>', "image/png"),
    (b"not an image", "image/webp"),
    (b"x" * (5 * 1024 * 1024 + 1), "image/png"),
], ids=["fake-svg", "invalid-bytes", "oversize"])
def test_invalid_or_oversize_upload_cannot_be_persisted(platform_branding, content, mime):
    env = platform_branding
    response = env.client.post(PATH + "/upload", headers=env.headers(), files={"file": ("icon.png", content, mime)})
    assert response.status_code in (400, 413, 422), response.text
    assert not list(env.upload_dir.rglob("*.png"))


@pytest.mark.parametrize("url", ["https://external.example/logo.png", "javascript:alert(1)", "/uploads/tenant.png",
    "/api/platform/branding/assets/../private.png"])
def test_save_rejects_urls_outside_managed_platform_assets(platform_branding, url):
    env = platform_branding
    response = env.client.put(PATH, headers=env.headers(), json={"logo_url": url, "favicon_url": ""})
    assert response.status_code in (400, 422), response.text


def test_oversized_dimensions_rejected_before_storage(platform_branding, monkeypatch):
    from backend.services.platform_branding_service import PlatformBrandingService
    env = platform_branding
    monkeypatch.setattr(PlatformBrandingService, "MAX_DIMENSION", 20)
    response = env.client.post(PATH + "/upload", headers=env.headers(),
        files={"file": ("large.png", image_bytes(), "image/png")})
    assert response.status_code == 422
    assert not list(env.upload_dir.rglob("*.png"))


def test_public_asset_rejects_symbolic_link(platform_branding):
    env = platform_branding
    url = upload(env)
    asset = env.upload_dir / "uploads" / "platform-branding" / url.rsplit("/", 1)[1]
    target = env.upload_dir / "private.png"
    target.write_bytes(asset.read_bytes())
    asset.unlink()
    try:
        asset.symlink_to(target)
    except OSError:
        pytest.skip("Windows account cannot create symbolic links")
    assert env.client.get(url).status_code == 404


def test_public_projection_does_not_publish_unexpected_persisted_fields(platform_branding):
    env = platform_branding
    env.db.execute(text("INSERT INTO site_config VALUES ('platform:branding', :content, CURRENT_TIMESTAMP)"),
        {"content": json.dumps({"logo_url": "", "favicon_url": "", "private_token": "must-not-publish"})})
    env.db.commit()
    result = env.client.get("/api/site-config", headers={"host": "app.telz.com.br"})
    assert result.status_code == 200
    assert "private_token" not in result.text and "must-not-publish" not in result.text
    assert result.json()["data"]["brand"]["faviconUrl"] == "/icons/telz.svg"
