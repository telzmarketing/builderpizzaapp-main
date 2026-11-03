from __future__ import annotations

import base64, hashlib, uuid
from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet
from sqlalchemy import and_, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.core.exceptions import DomainError
from backend.models.kds_production import ProductionAttempt, ProductionUnit
from backend.models.production_vision import (
    ProductionVisionCamera, ProductionVisionCaptureConfig, ProductionVisionCaptureEvent, ProductionVisionEvidenceHold, ProductionVisionIncident,
    ProductionVisionPhoto, ProductionVisionSession, ProductionVisionSettings,
    ProductionVisionStation, ProductionVisionZone, ProductionVisionZoneOccupancy,
)
from backend.schemas.production_vision import CameraIn, CaptureConfigIn, CaptureEventIn, EvidenceHoldIn, FinishIn, IncidentIn, OccupyZoneIn, PhotoIn, SessionIn, SettingsIn, StationIn, ZoneIn
from backend.core.kds_stations import KDS_STATION_LABELS


class ProductionVisionService:
    DEFAULTS = {"photos_per_session": 5, "max_width_px": 1280, "image_format": "webp", "image_quality": 80, "retention_days": 7}
    CAPTURE_GATEWAY_CONFIGURED = False

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

    def _capture_config(self, station_id: str) -> ProductionVisionCaptureConfig:
        self._station(station_id)
        item = self.db.query(ProductionVisionCaptureConfig).filter_by(tenant_id=self.tenant_id, station_id=station_id).one_or_none()
        if item is None:
            if station_id == "expedicao":
                defaults = {"milestone_1_name": "Foto início", "milestone_1_seconds": 5, "milestone_2_name": "Foto pizza pronta", "milestone_2_seconds": 40, "milestone_3_name": "Foto caixa fechada", "milestone_3_seconds": 0}
            else:
                defaults = {"milestone_1_name": "Foto 1", "milestone_1_seconds": 10, "milestone_2_name": "Foto 2", "milestone_2_seconds": 40, "milestone_3_name": "Foto 3 - Pronto", "milestone_3_seconds": 0}
            item = ProductionVisionCaptureConfig(id=str(uuid.uuid4()), tenant_id=self.tenant_id, station_id=station_id, **defaults)
            self.db.add(item)
            self.db.flush()
        return item

    @staticmethod
    def _capture_config_payload(item: ProductionVisionCaptureConfig) -> dict:
        return {
            "id": item.id, "tenant_id": item.tenant_id, "station_id": item.station_id,
            "milestone_1_name": item.milestone_1_name, "milestone_1_seconds": item.milestone_1_seconds,
            "milestone_2_name": item.milestone_2_name, "milestone_2_seconds": item.milestone_2_seconds,
            "milestone_3_name": item.milestone_3_name, "milestone_3_seconds": item.milestone_3_seconds,
            "enabled": item.enabled,
        }

    def capture_config(self, station_id: str) -> dict:
        return self._capture_config_payload(self._capture_config(station_id))

    def update_capture_config(self, body: CaptureConfigIn) -> dict:
        item = self._capture_config(body.station_id)
        for key in ("milestone_1_name", "milestone_1_seconds", "milestone_2_name", "milestone_2_seconds", "milestone_3_name", "milestone_3_seconds", "enabled"):
            setattr(item, key, getattr(body, key))
        self.db.flush()
        return self._capture_config_payload(item)

    @staticmethod
    def _capture_event_payload(item: ProductionVisionCaptureEvent) -> dict:
        return {"id": item.id, "session_id": item.session_id, "order_id": item.order_id, "production_unit_id": item.production_unit_id, "station_id": item.station_id, "milestone": item.milestone, "mode": item.mode, "status": item.status, "idempotency_key": item.idempotency_key, "photo_id": item.photo_id, "captured_at": item.captured_at, "reason": item.reason}

    def capture_event(self, session_id: str, body: CaptureEventIn, operator_id: str | None = None) -> dict:
        session = self.db.query(ProductionVisionSession).filter_by(tenant_id=self.tenant_id, id=session_id).one_or_none()
        if session is None:
            raise DomainError("Sessão não encontrada.", code="ProductionVisionSessionNotFound")
        existing = self.db.query(ProductionVisionCaptureEvent).filter_by(tenant_id=self.tenant_id, idempotency_key=body.idempotency_key).one_or_none()
        if existing:
            return self._capture_event_payload(existing)
        config = self._capture_config(session.station_id)
        unit = self.db.query(ProductionUnit).filter_by(tenant_id=self.tenant_id, id=session.production_unit_id).one_or_none()
        if unit is None:
            raise DomainError("Unidade de produção não encontrada.", code="ProductionUnitNotFound")
        photo_id = body.photo_id
        if photo_id:
            photo = self.db.query(ProductionVisionPhoto).filter_by(tenant_id=self.tenant_id, id=photo_id, session_id=session.id).one_or_none()
            if photo is None:
                raise DomainError("Foto não pertence à sessão.", code="ProductionVisionPhotoNotFound")
        if not config.enabled:
            status, reason = "unsupported", "capture_disabled"
        elif body.mode == "automatic" and not self.CAPTURE_GATEWAY_CONFIGURED:
            status, reason = "unsupported", "capture_gateway_not_configured"
        elif body.mode == "manual":
            status, reason = "captured", "manual_capture"
        else:
            status, reason = "pending", "awaiting_capture_gateway"
        now = datetime.now(timezone.utc) if status == "captured" else None
        item = ProductionVisionCaptureEvent(id=str(uuid.uuid4()), tenant_id=self.tenant_id, session_id=session.id, order_id=unit.order_id, production_unit_id=unit.id, station_id=session.station_id, milestone=body.milestone, mode=body.mode, status=status, idempotency_key=body.idempotency_key, photo_id=photo_id, captured_at=now, reason=reason)
        self.db.add(item)
        self.db.flush()
        return self._capture_event_payload(item)

    def capture_state(self, session_id: str) -> dict:
        session = self.db.query(ProductionVisionSession).filter_by(tenant_id=self.tenant_id, id=session_id).one_or_none()
        if session is None:
            raise DomainError("Sessão não encontrada.", code="ProductionVisionSessionNotFound")
        config = self._capture_config(session.station_id)
        events = {row.milestone: row for row in self.db.query(ProductionVisionCaptureEvent).filter_by(tenant_id=self.tenant_id, session_id=session.id).all()}
        milestones = []
        for index in (1, 2, 3):
            key = f"milestone_{index}"
            event = events.get(key)
            default_status = "unsupported" if not config.enabled or not self.CAPTURE_GATEWAY_CONFIGURED else "pending"
            milestones.append({"milestone": key, "name": getattr(config, f"{key}_name"), "seconds": getattr(config, f"{key}_seconds"), "status": event.status if event else default_status, "event": self._capture_event_payload(event) if event else None})
        return {"session_id": session.id, "order_id": self.db.query(ProductionUnit.order_id).filter_by(tenant_id=self.tenant_id, id=session.production_unit_id).scalar(), "production_unit_id": session.production_unit_id, "station_id": session.station_id, "gateway_configured": self.CAPTURE_GATEWAY_CONFIGURED, "milestones": milestones}

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
        referenced = set()
        for model in (ProductionVisionCamera, ProductionVisionZone, ProductionVisionSession):
            referenced.update(row[0] for row in self.db.query(model.station_id).filter(model.tenant_id == self.tenant_id).distinct().all() if row[0])
        managed_rows = self.db.query(ProductionVisionStation).filter_by(tenant_id=self.tenant_id).all()
        suppressed = {item.identifier for item in managed_rows if item.status != "active"}
        managed = [item for item in managed_rows if item.status == "active"]
        managed_by_id = {item.identifier: item for item in managed}
        camera_counts = dict(self.db.query(ProductionVisionCamera.station_id, func.count(ProductionVisionCamera.id)).filter_by(tenant_id=self.tenant_id).group_by(ProductionVisionCamera.station_id).all())
        active_session_counts = dict(self.db.query(ProductionVisionSession.station_id, func.count(ProductionVisionSession.id)).filter_by(tenant_id=self.tenant_id, status="active").group_by(ProductionVisionSession.station_id).all())
        result = []
        for station_id in sorted((referenced | set(managed_by_id)) - suppressed):
            item = managed_by_id.get(station_id)
            result.append({"id": station_id, "name": item.name if item else KDS_STATION_LABELS.get(station_id, station_id), "identifier": station_id, "station_type": item.station_type if item else ("legacy" if station_id in KDS_STATION_LABELS else "custom"), "status": "active", "protected": False, "fixed": False, "camera_count": camera_counts.get(station_id, 0), "active_sessions": active_session_counts.get(station_id, 0)})
        return result

    def _station(self, station_id: str | None, *, active: bool = True) -> dict:
        item = self.db.query(ProductionVisionStation).filter_by(tenant_id=self.tenant_id, identifier=station_id).one_or_none()
        if item is not None:
            if active and item.status != "active":
                raise DomainError("Estação inativa.", code="ProductionVisionStationInactive")
            return {"id": item.identifier, "name": item.name, "identifier": item.identifier, "station_type": item.station_type or "custom", "status": item.status, "protected": False, "fixed": False}
        if station_id in KDS_STATION_LABELS:
            return {"id": station_id, "name": KDS_STATION_LABELS[station_id], "identifier": station_id, "station_type": "legacy", "status": "active", "protected": False, "fixed": False}
        if item is None:
            raise DomainError("Estação não encontrada.", code="ProductionVisionStationNotFound")
        return {"id": item.identifier, "name": item.name, "identifier": item.identifier, "station_type": item.station_type or "custom", "status": item.status, "protected": False, "fixed": False}

    def save_station(self, body: StationIn, station_id: str | None = None) -> dict:
        item = self.db.query(ProductionVisionStation).filter_by(tenant_id=self.tenant_id, identifier=station_id).one_or_none() if station_id else None
        if station_id and item is None:
            if station_id not in KDS_STATION_LABELS:
                raise DomainError("Estação não encontrada.", code="ProductionVisionStationNotFound")
            item = ProductionVisionStation(id=str(uuid.uuid4()), tenant_id=self.tenant_id, identifier=station_id, name=KDS_STATION_LABELS[station_id], station_type="custom")
            self.db.add(item)
        if item is None:
            item = ProductionVisionStation(id=str(uuid.uuid4()), tenant_id=self.tenant_id)
            self.db.add(item)
        if item is not None and body.identifier != item.identifier:
            related = (
                self.db.query(ProductionVisionCamera.id).filter_by(tenant_id=self.tenant_id, station_id=item.identifier).first()
                or self.db.query(ProductionVisionZone.id).filter_by(tenant_id=self.tenant_id, station_id=item.identifier).first()
                or self.db.query(ProductionVisionSession.id).filter_by(tenant_id=self.tenant_id, station_id=item.identifier).first()
                or self.db.query(ProductionUnit.id).filter_by(tenant_id=self.tenant_id, station_id=item.identifier).first()
            )
            if related:
                raise DomainError("Estação em uso não pode ter o identificador alterado.", code="ProductionVisionStationInUse")
        item.name, item.identifier, item.status = body.name, body.identifier, body.status
        try:
            self.db.flush()
        except IntegrityError as exc:
            self.db.rollback()
            raise DomainError("Identificador de estação já cadastrado neste tenant.", code="ProductionVisionStationConflict") from exc
        return self._station(item.identifier, active=False)

    def delete_station(self, station_id: str) -> dict:
        item = self.db.query(ProductionVisionStation).filter_by(tenant_id=self.tenant_id, identifier=station_id).one_or_none()
        if item is None:
            if station_id not in KDS_STATION_LABELS:
                raise DomainError("Estação não encontrada.", code="ProductionVisionStationNotFound")
            item = ProductionVisionStation(id=str(uuid.uuid4()), tenant_id=self.tenant_id, identifier=station_id, name=KDS_STATION_LABELS[station_id], station_type="custom")
            self.db.add(item)
        related = self.db.query(ProductionVisionCamera.id).filter_by(tenant_id=self.tenant_id, station_id=item.identifier).first()
        related = related or self.db.query(ProductionVisionZone.id).filter_by(tenant_id=self.tenant_id, station_id=station_id).first()
        related = related or self.db.query(ProductionVisionSession.id).filter_by(tenant_id=self.tenant_id, station_id=item.identifier).first()
        related = related or self.db.query(ProductionUnit.id).filter_by(tenant_id=self.tenant_id, station_id=item.identifier).first()
        if related:
            item.status = "inactive"
        else:
            self.db.delete(item)
        self.db.flush()
        return {"deleted": True, "id": item.identifier}

    def zones(self) -> list[dict]:
        rows = self.db.query(ProductionVisionZone).filter_by(tenant_id=self.tenant_id).order_by(ProductionVisionZone.name).all()
        occupied = {x.zone_id for x in self.db.query(ProductionVisionZoneOccupancy).filter_by(tenant_id=self.tenant_id, released_at=None).all()}
        return [{"id": x.id, "name": x.name, "identifier": x.identifier, "station_id": x.station_id, "camera_id": x.camera_id, "status": x.status, "occupied": x.id in occupied} for x in rows]

    def save_camera(self, body: CameraIn, camera_id: str | None = None) -> dict:
        self._station(body.station_id)
        item = self.db.query(ProductionVisionCamera).filter_by(tenant_id=self.tenant_id, id=camera_id).one_or_none() if camera_id else None
        if camera_id and item is None: raise DomainError("Câmera não encontrada.", code="ProductionVisionCameraNotFound")
        if item is None: item = ProductionVisionCamera(id=str(uuid.uuid4()), tenant_id=self.tenant_id); self.db.add(item)
        for key in ("name", "identifier", "manufacturer", "model", "ip_address", "port", "protocol", "connection_url", "username", "resolution", "orientation", "installation_height_cm", "status", "station_id"): setattr(item, key, getattr(body, key))
        if body.password is not None: item.credentials_encrypted = Fernet(self._key()).encrypt(body.password.encode()).decode()
        try: self.db.flush()
        except IntegrityError as exc: self.db.rollback(); raise DomainError("Identificador de câmera já cadastrado neste tenant.", code="ProductionVisionCameraConflict") from exc
        return self._serialize_camera(item)

    def save_zone(self, body: ZoneIn, zone_id: str | None = None) -> dict:
        self._station(body.station_id)
        camera = self._camera(body.camera_id)
        if camera and camera.station_id != body.station_id:
            raise DomainError("Camera station mismatch.", code="ProductionVisionCameraStationMismatch")
        item = self.db.query(ProductionVisionZone).filter_by(tenant_id=self.tenant_id, id=zone_id).one_or_none() if zone_id else None
        if zone_id and item is None: raise DomainError("Zona não encontrada.", code="ProductionVisionZoneNotFound")
        if item is None: item = ProductionVisionZone(id=str(uuid.uuid4()), tenant_id=self.tenant_id); self.db.add(item)
        for key in ("name", "identifier", "station_id", "camera_id", "status"): setattr(item, key, getattr(body, key))
        try: self.db.flush()
        except IntegrityError as exc: self.db.rollback(); raise DomainError("Identificador de zona já cadastrado neste tenant.", code="ProductionVisionZoneConflict") from exc
        return next(x for x in self.zones() if x["id"] == item.id)

    def delete_zone(self, zone_id: str) -> dict:
        item = self.db.query(ProductionVisionZone).filter_by(tenant_id=self.tenant_id, id=zone_id).one_or_none()
        if item is None:
            raise DomainError("Zona não encontrada.", code="ProductionVisionZoneNotFound")
        if self.db.query(ProductionVisionZoneOccupancy.id).filter_by(tenant_id=self.tenant_id, zone_id=zone_id).first():
            raise DomainError("Zona possui ocupações e não pode ser excluída.", code="ProductionVisionZoneInUse")
        if self.db.query(ProductionVisionSession.id).filter_by(tenant_id=self.tenant_id, zone_id=zone_id).first():
            raise DomainError("Zona possui sessões e não pode ser excluída.", code="ProductionVisionZoneInUse")
        self.db.delete(item)
        self.db.flush()
        return {"deleted": True, "id": zone_id}

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
        self._station(station_id)
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
