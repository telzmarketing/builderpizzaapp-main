"""Platform-only identity persistence and image storage."""
from __future__ import annotations

import io
import json
import re
import warnings
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError
from sqlalchemy import text

from backend.core.exceptions import DomainError
from backend.schemas.platform_branding import PlatformBranding


class PlatformBrandingInvalid(DomainError):
    http_status = 422


class PlatformBrandingAssetNotFound(DomainError):
    http_status = 404


class PlatformBrandingFileTooLarge(DomainError):
    http_status = 413


class PlatformBrandingService:
    KEY = "platform:branding"
    ASSET_PREFIX = "/api/platform/branding/assets/"
    FILENAME = re.compile(r"^[0-9a-f]{32}\.png$")
    MAX_BYTES = 5 * 1024 * 1024
    MAX_PIXELS = 16_000_000
    MAX_DIMENSION = 4096

    def __init__(self, db=None):
        self.db = db

    @classmethod
    def _root(cls) -> Path:
        uploads = Path("uploads")
        root = uploads / "platform-branding"
        # The release installer intentionally links uploads to shared storage.
        if root.is_symlink():
            raise PlatformBrandingAssetNotFound("Arquivo nao encontrado.")
        resolved = root.resolve()
        if resolved.parent != uploads.resolve():
            raise PlatformBrandingAssetNotFound("Arquivo nao encontrado.")
        return resolved

    @classmethod
    def asset_path(cls, filename: str) -> Path:
        if not cls.FILENAME.fullmatch(filename):
            raise PlatformBrandingAssetNotFound("Arquivo nao encontrado.")
        root = cls._root()
        path = root / filename
        if path.is_symlink() or path.resolve().parent != root or not path.is_file():
            raise PlatformBrandingAssetNotFound("Arquivo nao encontrado.")
        return path

    @classmethod
    def _validate_url(cls, value: str) -> str:
        value = value.strip()
        if not value:
            return ""
        if not value.startswith(cls.ASSET_PREFIX):
            raise PlatformBrandingInvalid("Use uma imagem enviada para a marca do gestor.")
        filename = value[len(cls.ASSET_PREFIX):]
        if not cls.FILENAME.fullmatch(filename):
            raise PlatformBrandingInvalid("Use uma imagem enviada para a marca do gestor.")
        cls.asset_path(filename)
        return value

    def read_with_version(self):
        row = self.db.execute(
            text("SELECT content, updated_at FROM site_config WHERE id = :key"),
            {"key": self.KEY},
        ).fetchone()
        if row is None:
            return PlatformBranding(), None
        try:
            content = json.loads(row[0]) if row[0] else {}
            branding = PlatformBranding.model_validate(content)
        except (TypeError, ValueError):
            branding = PlatformBranding()
        return branding, row[1]

    def get(self) -> PlatformBranding:
        return self.read_with_version()[0]

    def save(self, payload: PlatformBranding) -> PlatformBranding:
        branding = PlatformBranding(
            logo_url=self._validate_url(payload.logo_url),
            favicon_url=self._validate_url(payload.favicon_url),
        )
        self.db.execute(text(
            "INSERT INTO site_config (id, content, updated_at) VALUES (:key, :content, CURRENT_TIMESTAMP) "
            "ON CONFLICT (id) DO UPDATE SET content = EXCLUDED.content, updated_at = CURRENT_TIMESTAMP"
        ), {"key": self.KEY, "content": json.dumps(branding.model_dump())})
        self.db.commit()
        return branding

    async def upload(self, file: UploadFile) -> dict:
        data = await file.read(self.MAX_BYTES + 1)
        if len(data) > self.MAX_BYTES:
            raise PlatformBrandingFileTooLarge("Imagem excede o limite de 5 MB.")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(data)) as image:
                    if image.format not in {"PNG", "JPEG", "WEBP"}:
                        raise PlatformBrandingInvalid("Use uma imagem PNG, JPEG ou WebP.")
                    width, height = image.size
                    if max(width, height) > self.MAX_DIMENSION or width * height > self.MAX_PIXELS:
                        raise PlatformBrandingInvalid("Imagem deve ter no maximo 4096 pixels por lado e 16 megapixels.")
                    image.load()
                    # Flatten animation and strip metadata by copying decoded pixels.
                    converted = image.convert("RGBA")
                    clean = Image.frombytes("RGBA", converted.size, converted.tobytes())
                    output = io.BytesIO()
                    clean.save(output, format="PNG")
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
            raise PlatformBrandingInvalid("Arquivo de imagem invalido.") from exc
        root = self._root()
        root.mkdir(parents=True, exist_ok=True)
        filename = f"{uuid4().hex}.png"
        with (root / filename).open("xb") as destination:
            destination.write(output.getvalue())
        return {"url": f"{self.ASSET_PREFIX}{filename}"}
