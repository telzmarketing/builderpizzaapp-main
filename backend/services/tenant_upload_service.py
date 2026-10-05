"""Ownership and ACL decisions for tenant-scoped uploads."""
from __future__ import annotations

from pathlib import PurePosixPath
from uuid import uuid4

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from backend.core.tenant_context import TenantContext
from backend.core.tenant_runtime import resolve_panel_tenant_context, resolve_public_tenant_context
from backend.models.admin import AdminUser
from backend.models.upload_asset import TenantUploadAsset
from backend.routes.admin_auth import authenticate_admin_token


class TenantUploadService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def storage_key(tenant_id: str, filename: str) -> str:
        return f"{tenant_id}/{filename}"

    def create_asset(
        self,
        *,
        context: TenantContext,
        admin: AdminUser,
        filename: str,
        original_filename: str,
        content_type: str,
        byte_size: int,
        visibility: str,
    ) -> TenantUploadAsset:
        if visibility not in {"public", "private"}:
            raise HTTPException(status_code=400, detail="Visibilidade de upload invalida.")
        asset = TenantUploadAsset(
            id=uuid4().hex,
            tenant_id=context.tenant_id,
            storage_key=self.storage_key(context.tenant_id, filename),
            original_filename=PurePosixPath(original_filename.replace("\\", "/")).name or filename,
            content_type=content_type,
            byte_size=byte_size,
            visibility=visibility,
            uploaded_by_admin_id=admin.id,
        )
        self.db.add(asset)
        self.db.flush()
        return asset

    def asset_for_storage_key(self, storage_key: str) -> TenantUploadAsset | None:
        return self.db.query(TenantUploadAsset).filter(TenantUploadAsset.storage_key == storage_key).one_or_none()

    def require_read_access(self, request: Request, storage_key: str) -> TenantUploadAsset:
        asset = self.asset_for_storage_key(storage_key)
        if asset is None:
            # Old URLs are intentionally not mapped to a tenant by filename.
            raise HTTPException(status_code=404, detail="Arquivo nao encontrado.")
        if asset.visibility == "public":
            context = resolve_public_tenant_context(request, self.db)
            if context is None or context.tenant_id != asset.tenant_id:
                raise HTTPException(status_code=404, detail="Arquivo nao encontrado.")
            return asset

        authorization = request.headers.get("authorization")
        try:
            admin = authenticate_admin_token(authorization, self.db)
            context = resolve_panel_tenant_context(request, self.db, admin)
        except HTTPException:
            raise HTTPException(status_code=404, detail="Arquivo nao encontrado.") from None
        if context is None or context.tenant_id != asset.tenant_id:
            raise HTTPException(status_code=404, detail="Arquivo nao encontrado.")
        return asset
