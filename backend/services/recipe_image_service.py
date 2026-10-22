"""Private, tenant-owned recipe reference images, independent of upload rollout flags."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
import re
import warnings
from uuid import uuid4

from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.models.upload_asset import TenantUploadAsset


IMAGE_PREFIX = "/api/gestao/inventory/recipe-images/"
PRIVATE_DIRECTORY = ".recipe-private"
MAX_IMAGE_BYTES = 5 * 1024 * 1024


class RecipeImageNotFound(DomainError):
    http_status = 404

    def __init__(self):
        super().__init__("Imagem de referência não encontrada.")


class RecipeImageInvalid(DomainError):
    http_status = 422


class RecipeImageService:
    def __init__(self, db: Session, tenant_id: str, actor_id: str | None = None):
        self.db, self.tenant_id, self.actor_id = db, tenant_id, actor_id

    def _asset(self, asset_id: str) -> TenantUploadAsset:
        if not re.fullmatch(r"[0-9a-f]{32}", asset_id):
            raise RecipeImageNotFound()
        asset = self.db.query(TenantUploadAsset).filter_by(
            id=asset_id, tenant_id=self.tenant_id, visibility="private",
        ).one_or_none()
        if asset is None or asset.storage_key != f"{PRIVATE_DIRECTORY}/{asset_id}.png" or asset.content_type != "image/png":
            raise RecipeImageNotFound()
        return asset

    def validate_reference(self, url: str | None) -> str | None:
        if url is None:
            return None
        if not url.startswith(IMAGE_PREFIX):
            raise RecipeImageInvalid("Use uma imagem privada enviada pelo cadastro da ficha.")
        asset = self._asset(url[len(IMAGE_PREFIX):])
        return f"{IMAGE_PREFIX}{asset.id}"

    def image_path(self, asset_id: str) -> Path:
        asset = self._asset(asset_id)
        root = Path("uploads").resolve()
        path = (root / asset.storage_key).resolve()
        if root not in path.parents or not path.is_file():
            raise RecipeImageNotFound()
        return path

    def create(self, data: bytes, content_type: str, original_filename: str | None) -> dict[str, str]:
        if content_type not in {"image/jpeg", "image/png", "image/webp", "image/gif"}:
            raise RecipeImageInvalid("Envie uma imagem JPEG, PNG, WebP ou GIF.")
        if not data or len(data) > MAX_IMAGE_BYTES:
            raise RecipeImageInvalid("A imagem deve ter no máximo 5 MB.")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(data)) as image:
                    if image.format not in {"JPEG", "PNG", "WEBP", "GIF"} or image.width * image.height > 16_000_000:
                        raise RecipeImageInvalid("Imagem inválida ou maior que 16 megapixels.")
                    image.load()
                    output = BytesIO()
                    # Re-encode raster pixels: no client filename, metadata, or active content is served.
                    image.convert("RGBA" if "A" in image.getbands() else "RGB").save(output, format="PNG")
                    encoded = output.getvalue()
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
            raise RecipeImageInvalid("O conteúdo enviado não é uma imagem válida.") from exc
        if len(encoded) > 20 * 1024 * 1024:
            raise RecipeImageInvalid("Imagem processada excede o limite de armazenamento.")
        asset_id = uuid4().hex
        key = f"{PRIVATE_DIRECTORY}/{asset_id}.png"
        root = Path("uploads").resolve()
        destination = (root / key).resolve()
        if root not in destination.parents:
            raise RecipeImageInvalid("Diretório privado inválido.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        asset = TenantUploadAsset(
            id=asset_id, tenant_id=self.tenant_id, storage_key=key,
            original_filename=Path((original_filename or "referencia.png").replace("\\", "/")).name[:255],
            content_type="image/png", byte_size=len(encoded), visibility="private",
            uploaded_by_admin_id=self.actor_id,
        )
        try:
            destination.write_bytes(encoded)
            self.db.add(asset)
            self.db.commit()
        except Exception:
            self.db.rollback()
            destination.unlink(missing_ok=True)
            raise
        return {"url": f"{IMAGE_PREFIX}{asset_id}"}
