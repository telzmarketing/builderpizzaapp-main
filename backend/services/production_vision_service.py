from __future__ import annotations

import base64
import hashlib
import uuid
from datetime import datetime, timezone

from cryptography.fernet import Fernet
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.core.exceptions import DomainError
from backend.models.kds_production import ProductionUnit
from backend.models.production_vision import ProductionVisionCamera, ProductionVisionPhoto, ProductionVisionSession
from backend.schemas.production_vision import CameraIn, FinishIn, PhotoIn, SessionIn


class ProductionVisionService:
    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id

    def _key(self) -> bytes:
        secret = get_settings().JWT_SECRET_KEY
        return base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())

    def _serialize_camera(self, camera: ProductionVisionCamera) -> dict:
        return {"id": camera.id, "name": camera.name, "identifier": camera.identifier, "manufacturer": camera.manufacturer, "model": camera.model, "ip_address": camera.ip_address, "port": camera.port, "protocol": camera.protocol, "station_id": camera.station_id, "resolution": camera.resolution, "orientation": camera.orientation, "installation_height_cm": camera.installation_height_cm, "status": camera.status, "last_connected_at": camera.last_connected_at, "has_credentials": bool(camera.credentials_encrypted)}

    def dashboard(self) -> dict:
        q = self.db.query
        return {"cameras_online": q(ProductionVisionCamera).filter_by(tenant_id=self.tenant_id, status="active").count(), "cameras_offline": q(ProductionVisionCamera).filter_by(tenant_id=self.tenant_id, status="inactive").count(), "sessions_active": q(ProductionVisionSession).filter_by(tenant_id=self.tenant_id, status="active").count(), "sessions_complete": q(ProductionVisionSession).filter_by(tenant_id=self.tenant_id, status="complete").count(), "sessions_partial": q(ProductionVisionSession).filter_by(tenant_id=self.tenant_id, status="partial").count(), "photos_captured": q(ProductionVisionPhoto).filter_by(tenant_id=self.tenant_id).count()}

    def cameras(self) -> list[dict]:
        return [self._serialize_camera(x) for x in self.db.query(ProductionVisionCamera).filter_by(tenant_id=self.tenant_id).order_by(ProductionVisionCamera.name).all()]

    def stations(self) -> list[dict]:
        rows = self.db.query(ProductionUnit.station_id).filter(ProductionUnit.tenant_id == self.tenant_id).distinct().order_by(ProductionUnit.station_id).all()
        return [{"id": row[0], "name": row[0]} for row in rows]

    def save_camera(self, body: CameraIn, camera_id: str | None = None) -> dict:
        camera = self.db.query(ProductionVisionCamera).filter_by(tenant_id=self.tenant_id, id=camera_id).one_or_none() if camera_id else None
        if camera_id and camera is None:
            raise DomainError("Câmera não encontrada.", code="ProductionVisionCameraNotFound")
        if camera is None:
            camera = ProductionVisionCamera(id=str(uuid.uuid4()), tenant_id=self.tenant_id)
            self.db.add(camera)
        for field in ("name", "identifier", "manufacturer", "model", "ip_address", "port", "protocol", "connection_url", "username", "resolution", "orientation", "installation_height_cm", "status", "station_id"):
            setattr(camera, field, getattr(body, field))
        if body.password is not None:
            camera.credentials_encrypted = Fernet(self._key()).encrypt(body.password.encode()).decode()
        try:
            self.db.flush()
        except Exception as exc:
            self.db.rollback()
            raise DomainError("Identificador de câmera já cadastrado neste tenant.", code="ProductionVisionCameraConflict") from exc
        return self._serialize_camera(camera)

    def create_session(self, body: SessionIn, operator_id: str) -> dict:
        unit = self.db.query(ProductionUnit).filter_by(tenant_id=self.tenant_id, id=body.production_unit_id).one_or_none()
        if unit is None:
            raise DomainError("Unidade de produção não encontrada.", code="ProductionUnitNotFound")
        if body.idempotency_key:
            existing = self.db.query(ProductionVisionSession).filter_by(tenant_id=self.tenant_id, idempotency_key=body.idempotency_key).one_or_none()
            if existing:
                return self.session(existing)
        session = ProductionVisionSession(id=str(uuid.uuid4()), tenant_id=self.tenant_id, production_unit_id=unit.id, stage=body.stage, operator_id=operator_id, idempotency_key=body.idempotency_key, expected_photo_count=body.expected_photo_count)
        self.db.add(session)
        self.db.flush()
        return self.session(session)

    def session(self, session: ProductionVisionSession) -> dict:
        return {"id": session.id, "production_unit_id": session.production_unit_id, "stage": session.stage, "operator_id": session.operator_id, "status": session.status, "started_at": session.started_at, "completed_at": session.completed_at, "expected_photo_count": session.expected_photo_count, "photo_count": self.db.query(ProductionVisionPhoto).filter_by(tenant_id=self.tenant_id, session_id=session.id).count()}

    def add_photo(self, session_id: str, body: PhotoIn) -> dict:
        session = self.db.query(ProductionVisionSession).filter_by(tenant_id=self.tenant_id, id=session_id).one_or_none()
        if session is None:
            raise DomainError("Sessão não encontrada.", code="ProductionVisionSessionNotFound")
        if session.status != "active":
            raise DomainError("Sessão já finalizada.", code="ProductionVisionSessionClosed")
        existing = self.db.query(ProductionVisionPhoto).filter_by(tenant_id=self.tenant_id, session_id=session_id, idempotency_key=body.idempotency_key).one_or_none()
        if existing:
            return self.photo(existing)
        photo = ProductionVisionPhoto(id=str(uuid.uuid4()), tenant_id=self.tenant_id, session_id=session_id, idempotency_key=body.idempotency_key, captured_at=body.captured_at or datetime.now(timezone.utc), original_storage_key=body.original_storage_key, processed_storage_key=body.processed_storage_key, content_type=body.content_type, width=body.width, height=body.height, byte_size=body.byte_size, is_final=body.is_final, metadata_json=body.metadata)
        self.db.add(photo)
        self.db.flush()
        return self.photo(photo)

    def photo(self, photo: ProductionVisionPhoto) -> dict:
        return {"id": photo.id, "session_id": photo.session_id, "idempotency_key": photo.idempotency_key, "captured_at": photo.captured_at, "original_storage_key": photo.original_storage_key, "processed_storage_key": photo.processed_storage_key, "content_type": photo.content_type, "width": photo.width, "height": photo.height, "byte_size": photo.byte_size, "is_final": photo.is_final, "metadata": photo.metadata_json}

    def finish(self, session_id: str, body: FinishIn) -> dict:
        session = self.db.query(ProductionVisionSession).filter_by(tenant_id=self.tenant_id, id=session_id).one_or_none()
        if session is None:
            raise DomainError("Sessão não encontrada.", code="ProductionVisionSessionNotFound")
        if session.status != "active":
            return self.session(session)
        photos = self.db.query(ProductionVisionPhoto).filter_by(tenant_id=self.tenant_id, session_id=session_id).all()
        if body.status == "complete" and not any(p.is_final for p in photos):
            raise DomainError("Sessão completa exige fotografia final.", code="ProductionVisionFinalPhotoRequired")
        session.status = body.status
        session.completed_at = datetime.now(timezone.utc)
        self.db.flush()
        return self.session(session)
