from backend.models.upload_asset import TenantUploadAsset, TenantUploadLegacyReference


def _index_columns(model) -> dict[str, tuple[str, ...]]:
    return {
        index.name: tuple(column.name for column in index.columns)
        for index in model.__table__.indexes
    }


def test_upload_asset_model_declares_the_tenant_lookup_and_unique_storage_indexes():
    indexes = _index_columns(TenantUploadAsset)

    assert indexes["ix_tenant_upload_assets_tenant_id"] == ("tenant_id",)
    assert indexes["ix_tenant_upload_assets_tenant_visibility"] == ("tenant_id", "visibility")
    assert indexes["uq_tenant_upload_assets_storage_key"] == ("storage_key",)
    assert next(index for index in TenantUploadAsset.__table__.indexes if index.name == "uq_tenant_upload_assets_storage_key").unique


def test_legacy_reference_model_declares_tenant_lookup_and_reference_uniqueness():
    indexes = _index_columns(TenantUploadLegacyReference)

    assert indexes["ix_tenant_upload_legacy_references_tenant"] == ("tenant_id",)
    assert indexes["uq_tenant_upload_legacy_reference"] == ("source_table", "source_id", "source_column")
    assert next(index for index in TenantUploadLegacyReference.__table__.indexes if index.name == "uq_tenant_upload_legacy_reference").unique
