import base64
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.config import PROJECT_ROOT
from backend.database import Base
from backend.models.admin import AdminUser
from backend.models.gestor import GestorMultimodalArtifact, GestorMultimodalAudit
from backend.models.membership import TenantMembership
from backend.models.tenant import Tenant
from backend.models.upload_asset import TenantUploadAsset
from backend.schemas.gestor import GestorMultimodalIn, GestorMultimodalReviewIn
from backend.services.gestor_service import GestorMultimodalInvalid, GestorService


@pytest.fixture()
def multimodal_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[
        Tenant.__table__, AdminUser.__table__, TenantMembership.__table__, TenantUploadAsset.__table__,
        GestorMultimodalArtifact.__table__, GestorMultimodalAudit.__table__,
    ])
    db = sessionmaker(bind=engine)()
    tenant_id, other_tenant_id, admin_id = str(uuid4()), str(uuid4()), str(uuid4())
    db.add_all([
        Tenant(id=tenant_id, slug=f"mm-{tenant_id[:8]}", name="Multimodal", status="active"),
        AdminUser(id=admin_id, email=f"mm-{admin_id[:8]}@test.invalid", name="Gestor", password_hash="unused", active=True),
        TenantMembership(id=str(uuid4()), tenant_id=tenant_id, user_id=admin_id, role="owner", status="active", is_default=True),
    ])
    db.commit()
    created_paths: list[Path] = []
    try:
        yield db, tenant_id, other_tenant_id, admin_id, created_paths
    finally:
        for path in created_paths:
            if path.exists():
                path.unlink()
        db.close()
        engine.dispose()


def _service(db, tenant_id, admin_id):
    return GestorService(db, tenant_id, admin_id)


def _track_path(artifact, created_paths):
    path = PROJECT_ROOT / "uploads" / artifact.storage_key
    created_paths.append(path)


def test_text_image_and_document_are_tenant_scoped_and_safe(multimodal_db):
    db, tenant_id, _other_tenant_id, admin_id, created_paths = multimodal_db
    service = _service(db, tenant_id, admin_id)

    text, replay = service.ingest_multimodal(GestorMultimodalIn(
        media_type="text", text="Resumo de vendas", idempotency_key="text-1",
    ))
    assert replay is False
    assert text.status == "processed"
    assert text.extracted_text == "Resumo de vendas"
    _track_path(text, created_paths)

    image, _ = service.ingest_multimodal(GestorMultimodalIn(
        media_type="image", mime_type="image/png", filename="cardapio.png",
        content_base64=base64.b64encode(b"png-bytes").decode(), idempotency_key="image-1",
    ))
    assert image.status == "review_required"
    assert image.review_required is True
    assert image.storage_key.startswith(f"{tenant_id}/")
    asset = db.query(TenantUploadAsset).filter(TenantUploadAsset.id == image.storage_asset_id).one()
    assert asset.tenant_id == tenant_id and asset.visibility == "private"
    _track_path(image, created_paths)

    document, _ = service.ingest_multimodal(GestorMultimodalIn(
        media_type="document", mime_type="application/pdf", filename="relatorio.pdf",
        content_base64=base64.b64encode(b"%PDF manual review").decode(), idempotency_key="document-1",
    ))
    assert document.status == "review_required"
    assert document.review_required is True
    assert document.metadata_json["automatic_mutation"] is False
    _track_path(document, created_paths)

    assert len(db.query(GestorMultimodalAudit).filter(GestorMultimodalAudit.tenant_id == tenant_id).all()) >= 6
    assert _service(db, _other_tenant_id, admin_id).list_multimodal() == []


def test_audio_uses_canonical_service_and_low_confidence_requires_review(multimodal_db, monkeypatch):
    db, tenant_id, _other_tenant_id, admin_id, created_paths = multimodal_db

    def fake_canonical_audio(self, artifact, media_url):
        assert media_url.startswith("/uploads/")
        artifact.processor = "AgenteWhatsAppAudioService"
        artifact.extracted_text = "oi"
        artifact.confidence = 0.2
        artifact.status = "review_required"
        artifact.review_required = True
        artifact.review_reason = "Baixa confianca na transcricao; confirme ou corrija o texto."

    monkeypatch.setattr(GestorService, "_process_multimodal_audio", fake_canonical_audio)
    artifact, _ = _service(db, tenant_id, admin_id).ingest_multimodal(GestorMultimodalIn(
        media_type="audio", mime_type="audio/ogg", filename="voz.ogg",
        content_base64=base64.b64encode(b"audio-bytes").decode(), idempotency_key="audio-1",
    ))
    assert artifact.processor == "AgenteWhatsAppAudioService"
    assert artifact.extracted_text == "oi"
    assert artifact.status == "review_required"
    assert artifact.review_required is True
    _track_path(artifact, created_paths)


def test_idempotency_review_and_validation(multimodal_db):
    db, tenant_id, _other_tenant_id, admin_id, created_paths = multimodal_db
    service = _service(db, tenant_id, admin_id)
    body = GestorMultimodalIn(
        media_type="image", mime_type="image/jpeg", content_base64=base64.b64encode(b"jpeg").decode(),
        idempotency_key="same-request",
    )
    first, replay = service.ingest_multimodal(body)
    second, replay_again = service.ingest_multimodal(body)
    assert first.id == second.id and replay is False and replay_again is True
    assert db.query(GestorMultimodalArtifact).count() == 1
    _track_path(first, created_paths)

    reviewed = service.review_multimodal(first.id, GestorMultimodalReviewIn(
        approved=True, note="Conferido pelo administrador",
    ))
    assert reviewed.status == "reviewed" and reviewed.review_required is False
    assert db.query(GestorMultimodalAudit).filter(GestorMultimodalAudit.artifact_id == first.id).count() == 3

    with pytest.raises(GestorMultimodalInvalid, match="MIME"):
        service.ingest_multimodal(GestorMultimodalIn(
            media_type="audio", mime_type="application/pdf", content_base64="eA==", idempotency_key="bad-mime",
        ))
    with pytest.raises(GestorMultimodalInvalid, match="base64"):
        service.ingest_multimodal(GestorMultimodalIn(
            media_type="image", mime_type="image/png", content_base64="not-base64", idempotency_key="bad-base64",
        ))
