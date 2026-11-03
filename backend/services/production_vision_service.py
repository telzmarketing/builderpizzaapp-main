from __future__ import annotations

import base64, hashlib, uuid
from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet
from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.core.exceptions import DomainError
from backend.models.kds_production import ProductionAttempt, ProductionUnit
from backend.models.production_vision import (
    ProductionVisionCamera, ProductionVisionEvidenceHold, ProductionVisionIncident,
    ProductionVisionPhoto, ProductionVisionSession, ProductionVisionSettings,
    ProductionVisionZone, ProductionVisionZoneOccupancy,
)
from backend.schemas.production_vision import CameraIn, EvidenceHoldIn, FinishIn, IncidentIn, OccupyZoneIn, PhotoIn, SessionIn, SettingsIn, ZoneIn
from backend.core.kds_stations import KDS_STATION_LABELS, LEGACY_STATION_IDS, PIZZA_STATION_IDS, is_supported_station


class ProductionVisionService:
    DEFAULTS = {"photos_per_session": 5, "max_width_px": 1280, "image_format": "webp", "image_quality": 80, "retention_days": 7}

    def __init__(self, db: Session, tenant_id: str):
        self.db, self.tenant_id = db, tenant_id

    def _key(self) -> bytes:
        return base64.urlsafe_b64encode(hashlib.sha256(get_settings().JWT_SECRET_KEY.encode()).digest())

    def _settings(self, create: bool = True) -> ProductionVisionSettings | None:
        item = self.db.query(ProductionVisionSettings).filter_by(tenant_id=self.tenant_id).one_or_none()
        if item is None and create:
            item = ProductionVisionSettings(id=str(uuid.uuid4()), tenant_id=self.tenant_id, **self.DEFAULTS)
            self.db.add(item); self.db.flush()
        return item

    def settings(self) -> dict:
        item = self._settings()
        return {"id": item.id, "tenant_id": item.tenant_id, **{key: getattr(item, key) for key in self.DEFAULTS}}

    def update_settings(self, body: SettingsIn) -> dict:
        item = self._settings()
        for key in self.DEFAULTS: setattr(item, key, getattr(body, key))
        self.db.flush()
        return self.settings()

    def _camera(self, camera_id: str | None) -> ProductionVisionCamera | None:
        if not camera_id: return None
        item = self.db.query(ProductionVisionCamera).filter_by(tenant_id=self.tenant_id, id=camera_id).one_or_none()
        if item is None: raise DomainError("Câmera não encontrada.", code="ProductionVisionCameraNotFound")
        return item

    def _zone(self, zone_id: str | None) -> ProductionVisionZone | None:
        if not zone_id: return None
        item = self.db.query(ProductionVisionZone).filter_by(tenant_id=self.tenant_id, id=zone_id).one_or_none()
        if item is None: raise DomainError("Zona não encontrada.", code="ProductionVisionZoneNotFound")
        if item.status != "active": raise DomainError("Zona inativa.", code="ProductionVisionZoneInactive")
        return item

    def _serialize_camera(self, item: ProductionVisionCamera) -> dict:
        return {"id": item.id, "name": item.name, "identifier": item.identifier, "manufacturer": item.manufacturer, "model": item.model, "ip_address": item.ip_address, "port": item.port, "protocol": item.protocol, "station_id": item.station_id, "resolution": item.resolution, "orientation": item.orientation, "installation_height_cm": item.installation_height_cm, "status": item.status, "last_connected_at": item.last_connected_at, "has_credentials": bool(item.credentials_encrypted)}

    def dashboard(self) -> dict:
        q = self.db.query
        return {"cameras_online": q(ProductionVisionCamera).filter_by(tenant_id=self.tenant_id, status="active").count(), "cameras_offline": q(ProductionVisionCamera).filter_by(tenant_id=self.tenant_id, status="inactive").count(), "sessions_active": q(ProductionVisionSession).filter_by(tenant_id=self.tenant_id, status="active").count(), "sessions_complete": q(ProductionVisionSession).filter_by(tenant_id=self.tenant_id, status="complete").count(), "sessions_partial": q(ProductionVisionSession).filter_by(tenant_id=self.tenant_id, status="partial").count(), "photos_captured": q(ProductionVisionPhoto).filter_by(tenant_id=self.tenant_id).count(), "incidents_open": q(ProductionVisionIncident).filter_by(tenant_id=self.tenant_id, status="open").count(), "zones_occupied": q(ProductionVisionZoneOccupancy).filter(ProductionVisionZoneOccupancy.tenant_id == self.tenant_id, ProductionVisionZoneOccupancy.released_at.is_(None)).count()}

    def cameras(self) -> list[dict]:
        return [self._serialize_camera(x) for x in self.db.query(ProductionVisionCamera).filter_by(tenant_id=self.tenant_id).order_by(ProductionVisionCamera.name).all()]

    def stations(self) -> list[dict]:
        rows = {row[0] for row in self.db.query(ProductionUnit.station_id).filter(ProductionUnit.tenant_id == self.tenant_id).distinct().all()}
        # Fixed pizza benches are always available for camera/zone assignment;
        # legacy stations remain listed for existing tenants and records.
        station_ids = list(PIZZA_STATION_IDS) + [station for station in LEGACY_STATION_IDS if station in rows]
        station_ids.extend(sorted(rows - set(station_ids)))
        return [{"id": station_id, "name": KDS_STATION_LABELS.get(station_id, station_id)} for station_id in station_ids]

    def zones(self) -> list[dict]:
        rows = self.db.query(ProductionVisionZone).filter_by(tenant_id=self.tenant_id).order_by(ProductionVisionZone.name).all()
        occupied = {x.zone_id for x in self.db.query(ProductionVisionZoneOccupancy).filter_by(tenant_id=self.tenant_id, released_at=None).all()}
        return [{"id": x.id, "name": x.name, "identifier": x.identifier, "station_id": x.station_id, "camera_id": x.camera_id, "status": x.status, "occupied": x.id in occupied} for x in rows]

    def save_camera(self, body: CameraIn, camera_id: str | None = None) -> dict:
        if not is_supported_station(body.station_id):
            raise DomainError("Estação operacional inválida.", code="ProductionVisionStationInvalid")
        item = self.db.query(ProductionVisionCamera).filter_by(tenant_id=self.tenant_id, id=camera_id).one_or_none() if camera_id else None
        if camera_id and item is None: raise DomainError("Câmera não encontrada.", code="ProductionVisionCameraNotFound")
        if item is None: item = ProductionVisionCamera(id=str(uuid.uuid4()), tenant_id=self.tenant_id); self.db.add(item)
        for key in ("name", "identifier", "manufacturer", "model", "ip_address", "port", "protocol", "connection_url", "username", "resolution", "orientation", "installation_height_cm", "status", "station_id"): setattr(item, key, getattr(body, key))
        if body.password is not None: item.credentials_encrypted = Fernet(self._key()).encrypt(body.password.encode()).decode()
        try: self.db.flush()
        except IntegrityError as exc: self.db.rollback(); raise DomainError("Identificador de câmera já cadastrado neste tenant.", code="ProductionVisionCameraConflict") from exc
        return self._serialize_camera(item)

    def save_zone(self, body: ZoneIn, zone_id: str | None = None) -> dict:
        if not is_supported_station(body.station_id):
            raise DomainError("Estação operacional inválida.", code="ProductionVisionStationInvalid")
        self._camera(body.camera_id)
        item = self.db.query(ProductionVisionZone).filter_by(tenant_id=self.tenant_id, id=zone_id).one_or_none() if zone_id else None
        if zone_id and item is None: raise DomainError("Zona não encontrada.", code="ProductionVisionZoneNotFound")
        if item is None: item = ProductionVisionZone(id=str(uuid.uuid4()), tenant_id=self.tenant_id); self.db.add(item)
        for key in ("name", "identifier", "station_id", "camera_id", "status"): setattr(item, key, getattr(body, key))
        try: self.db.flush()
        except IntegrityError as exc: self.db.rollback(); raise DomainError("Identificador de zona já cadastrado neste tenant.", code="ProductionVisionZoneConflict") from exc
        return next(x for x in self.zones() if x["id"] == item.id)

    def occupy_zone(self, zone_id: str, body: OccupyZoneIn) -> dict:
        zone = self._zone(zone_id)
        session = self.db.query(ProductionVisionSession).filter_by(tenant_id=self.tenant_id, id=body.session_id).one_or_none()
        if session is None:
            raise DomainError("Sessão não encontrada.", code="ProductionVisionSessionNotFound")
        existing = self.db.query(ProductionVisionZoneOccupancy).filter_by(tenant_id=self.tenant_id, idempotency_key=body.idempotency_key).one_or_none()
        if existing:
            return {"id": existing.id, "zone_id": existing.zone_id, "session_id": existing.session_id, "released_at": existing.released_at}
        occupied = self.db.query(ProductionVisionZoneOccupancy).filter_by(tenant_id=self.tenant_id, zone_id=zone.id, released_at=None).with_for_update().one_or_none()
        if occupied and occupied.session_id != session.id:
            self._incident("zone_occupied", "Zona já ocupada por outra sessão.", session_id=session.id, zone_id=zone.id)
            raise DomainError("Zona já ocupada.", code="ProductionVisionZoneOccupied")
        item = ProductionVisionZoneOccupancy(id=str(uuid.uuid4()), tenant_id=self.tenant_id, zone_id=zone.id, session_id=session.id, idempotency_key=body.idempotency_key)
        self.db.add(item); self.db.flush()
        return {"id": item.id, "zone_id": item.zone_id, "session_id": item.session_id, "released_at": item.released_at}

    def release_zone(self, zone_id: str, session_id: str) -> dict:
        self._zone(zone_id)
        item = self.db.query(ProductionVisionZoneOccupancy).filter_by(tenant_id=self.tenant_id, zone_id=zone_id, session_id=session_id, released_at=None).one_or_none()
        if item is not None:
            item.released_at = datetime.now(timezone.utc); self.db.flush()
        return {"released": item is not None, "zone_id": zone_id, "session_id": session_id}

    def create_session(self, body: SessionIn, operator_id: str) -> dict:
        unit = self.db.query(ProductionUnit).filter_by(tenant_id=self.tenant_id, id=body.production_unit_id).one_or_none()
        if unit is None: raise DomainError("Unidade de produção não encontrada.", code="ProductionUnitNotFound")
        if body.idempotency_key:
            existing = self.db.query(ProductionVisionSession).filter_by(tenant_id=self.tenant_id, idempotency_key=body.idempotency_key).one_or_none()
            if existing: return self.session(existing)
        attempt = None
        if body.production_attempt_id:
            attempt = self.db.query(ProductionAttempt).filter_by(tenant_id=self.tenant_id, id=body.production_attempt_id, production_unit_id=unit.id).one_or_none()
            if attempt is None: raise DomainError("Tentativa de produção não encontrada para a unidade.", code="ProductionVisionAttemptNotFound")
        station_id = body.station_id or unit.station_id
        if not is_supported_station(station_id):
            raise DomainError("Estação operacional inválida.", code="ProductionVisionStationInvalid")
        camera = self._camera(body.camera_id); zone = self._zone(body.zone_id)
        if zone and zone.station_id != station_id: raise DomainError("Zona não pertence à estação informada.", code="ProductionVisionZoneStationMismatch")
        current = self._settings()
        item = ProductionVisionSession(id=str(uuid.uuid4()), tenant_id=self.tenant_id, production_unit_id=unit.id, production_attempt_id=attempt.id if attempt else None, stage=body.stage, station_id=station_id, camera_id=camera.id if camera else None, zone_id=zone.id if zone else None, operator_id=operator_id, idempotency_key=body.idempotency_key, expected_photo_count=body.expected_photo_count or current.photos_per_session)
        self.db.add(item); self.db.flush()
        if zone:
            key = body.idempotency_key or item.id
            occupied = self.db.query(ProductionVisionZoneOccupancy).filter_by(tenant_id=self.tenant_id, zone_id=zone.id, released_at=None).with_for_update().one_or_none()
            if occupied and occupied.session_id != item.id: self._incident("zone_occupied", "Zona já ocupada por outra sessão.", session_id=item.id, zone_id=zone.id); self.db.rollback(); raise DomainError("Zona já ocupada.", code="ProductionVisionZoneOccupied")
            self.db.add(ProductionVisionZoneOccupancy(id=str(uuid.uuid4()), tenant_id=self.tenant_id, zone_id=zone.id, session_id=item.id, idempotency_key=key)); self.db.flush()
        return self.session(item)

    def session(self, item: ProductionVisionSession) -> dict:
        return {"id": item.id, "production_unit_id": item.production_unit_id, "production_attempt_id": item.production_attempt_id, "stage": item.stage, "station_id": item.station_id, "camera_id": item.camera_id, "zone_id": item.zone_id, "operator_id": item.operator_id, "status": item.status, "started_at": item.started_at, "completed_at": item.completed_at, "expected_photo_count": item.expected_photo_count, "photo_count": self.db.query(ProductionVisionPhoto).filter_by(tenant_id=self.tenant_id, session_id=item.id).count()}

    def add_photo(self, session_id: str, body: PhotoIn) -> dict:
        item = self.db.query(ProductionVisionSession).filter_by(tenant_id=self.tenant_id, id=session_id).one_or_none()
        if item is None: raise DomainError("Sessão não encontrada.", code="ProductionVisionSessionNotFound")
        if item.status != "active": raise DomainError("Sessão já finalizada.", code="ProductionVisionSessionClosed")
        existing = self.db.query(ProductionVisionPhoto).filter_by(tenant_id=self.tenant_id, session_id=session_id, idempotency_key=body.idempotency_key).one_or_none()
        if existing: return self.photo(existing)
        photo = ProductionVisionPhoto(id=str(uuid.uuid4()), tenant_id=self.tenant_id, session_id=session_id, idempotency_key=body.idempotency_key, captured_at=body.captured_at or datetime.now(timezone.utc), original_storage_key=body.original_storage_key, processed_storage_key=body.processed_storage_key, content_type=body.content_type, width=body.width, height=body.height, byte_size=body.byte_size, sha256=body.sha256, processing_status=body.processing_status, is_final=body.is_final, metadata_json=body.metadata)
        self.db.add(photo); self.db.flush(); return self.photo(photo)

    def photo(self, item: ProductionVisionPhoto) -> dict:
        return {"id": item.id, "session_id": item.session_id, "idempotency_key": item.idempotency_key, "captured_at": item.captured_at, "original_storage_key": item.original_storage_key, "processed_storage_key": item.processed_storage_key, "content_type": item.content_type, "width": item.width, "height": item.height, "byte_size": item.byte_size, "sha256": item.sha256, "processing_status": item.processing_status, "is_final": item.is_final, "metadata": item.metadata_json}

    def finish(self, session_id: str, body: FinishIn) -> dict:
        item = self.db.query(ProductionVisionSession).filter_by(tenant_id=self.tenant_id, id=session_id).one_or_none()
        if item is None: raise DomainError("Sessão não encontrada.", code="ProductionVisionSessionNotFound")
        if item.status != "active": return self.session(item)
        photos = self.db.query(ProductionVisionPhoto).filter_by(tenant_id=self.tenant_id, session_id=session_id).all()
        if body.status == "complete" and not any(p.is_final for p in photos): raise DomainError("Sessão completa exige fotografia final.", code="ProductionVisionFinalPhotoRequired")
        item.status, item.completed_at = body.status, datetime.now(timezone.utc)
        self.db.query(ProductionVisionZoneOccupancy).filter_by(tenant_id=self.tenant_id, session_id=item.id, released_at=None).update({"released_at": item.completed_at}, synchronize_session=False)
        self.db.flush(); return self.session(item)

    def history(self, session_id: str | None = None, photo_id: str | None = None, limit: int = 100) -> list[dict]:
        if photo_id:
            photo = self.db.query(ProductionVisionPhoto).filter_by(tenant_id=self.tenant_id, id=photo_id).one_or_none()
            session_id = photo.session_id if photo else "__missing__"
        query = self.db.query(ProductionVisionSession).filter_by(tenant_id=self.tenant_id)
        if session_id: query = query.filter_by(id=session_id)
        items = query.order_by(ProductionVisionSession.started_at.desc()).limit(min(limit, 500)).all()
        return [{**self.session(item), "photos": [self.photo(p) for p in self.db.query(ProductionVisionPhoto).filter_by(tenant_id=self.tenant_id, session_id=item.id).order_by(ProductionVisionPhoto.captured_at).all()], "incidents": self.incidents(item.id)} for item in items]

    def _incident(self, code: str, message: str, session_id: str | None = None, photo_id: str | None = None, zone_id: str | None = None, details: dict | None = None) -> ProductionVisionIncident:
        item = ProductionVisionIncident(id=str(uuid.uuid4()), tenant_id=self.tenant_id, session_id=session_id, photo_id=photo_id, zone_id=zone_id, code=code, message=message, details_json=details or {})
        self.db.add(item); self.db.flush(); return item

    def add_incident(self, body: IncidentIn) -> dict:
        item = self._incident(body.code, body.message, body.session_id, body.photo_id, body.zone_id, body.details)
        return self.incident(item)

    def incident(self, item: ProductionVisionIncident) -> dict:
        return {"id": item.id, "code": item.code, "message": item.message, "status": item.status, "session_id": item.session_id, "photo_id": item.photo_id, "zone_id": item.zone_id, "details": item.details_json, "created_at": item.created_at, "resolved_at": item.resolved_at}

    def incidents(self, session_id: str | None = None) -> list[dict]:
        query = self.db.query(ProductionVisionIncident).filter_by(tenant_id=self.tenant_id)
        if session_id: query = query.filter_by(session_id=session_id)
        return [self.incident(x) for x in query.order_by(ProductionVisionIncident.created_at.desc()).limit(500).all()]

    def holds(self) -> list[dict]:
        rows = self.db.query(ProductionVisionEvidenceHold).filter_by(tenant_id=self.tenant_id).order_by(ProductionVisionEvidenceHold.created_at.desc()).limit(500).all()
        return [self.hold(row) for row in rows]

    def add_hold(self, body: EvidenceHoldIn, user_id: str) -> dict:
        existing = self.db.query(ProductionVisionEvidenceHold).filter_by(tenant_id=self.tenant_id, hold_key=body.hold_key).one_or_none()
        if existing: return self.hold(existing)
        if not body.session_id and not body.photo_id: raise DomainError("Informe sessão ou foto para preservar.", code="ProductionVisionHoldTargetRequired")
        item = ProductionVisionEvidenceHold(id=str(uuid.uuid4()), tenant_id=self.tenant_id, hold_key=body.hold_key, session_id=body.session_id, photo_id=body.photo_id, reason=body.reason, created_by=user_id)
        self.db.add(item); self.db.flush(); return self.hold(item)

    def release_hold(self, hold_key: str) -> dict:
        item = self.db.query(ProductionVisionEvidenceHold).filter_by(tenant_id=self.tenant_id, hold_key=hold_key).one_or_none()
        if item is None: raise DomainError("Evidence hold não encontrado.", code="ProductionVisionHoldNotFound")
        item.released_at = item.released_at or datetime.now(timezone.utc); self.db.flush(); return self.hold(item)

    def hold(self, item: ProductionVisionEvidenceHold) -> dict:
        return {"id": item.id, "hold_key": item.hold_key, "session_id": item.session_id, "photo_id": item.photo_id, "reason": item.reason, "created_at": item.created_at, "released_at": item.released_at}

    def retention_dry_run(self) -> dict:
        cutoff = datetime.now(timezone.utc) - timedelta(days=self._settings().retention_days)
        photos = self.db.query(ProductionVisionPhoto).filter(ProductionVisionPhoto.tenant_id == self.tenant_id, ProductionVisionPhoto.captured_at < cutoff).all()
        held_session = {x.session_id for x in self.db.query(ProductionVisionEvidenceHold).filter_by(tenant_id=self.tenant_id, released_at=None).filter(ProductionVisionEvidenceHold.session_id.isnot(None)).all()}
        held_photo = {x.photo_id for x in self.db.query(ProductionVisionEvidenceHold).filter_by(tenant_id=self.tenant_id, released_at=None).filter(ProductionVisionEvidenceHold.photo_id.isnot(None)).all()}
        protected = [p for p in photos if p.session_id in held_session or p.id in held_photo]
        eligible = [p for p in photos if p not in protected]
        return {"dry_run": True, "retention_days": self._settings().retention_days, "cutoff": cutoff, "eligible_count": len(eligible), "protected_count": len(protected), "eligible_photo_ids": [p.id for p in eligible], "protected_photo_ids": [p.id for p in protected], "files_deleted": 0, "metadata_preserved": True}

    def diagnostics(self) -> dict:
        return {"gateway": {"configured": False, "status": "not_configured", "hardware_proof": False}, "storage": {"file_deletion_enabled": False, "originals_preserved": True}, "retention": self.retention_dry_run(), "open_incidents": len(self.incidents())}
