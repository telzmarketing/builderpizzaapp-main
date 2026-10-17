"""Read and update the existing per-tenant exit popup singleton."""
from datetime import datetime, timezone
import sqlite3

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.models.exit_popup import ExitPopupConfig


def _is_creation_conflict(error: IntegrityError) -> bool:
    original = error.orig
    constraint = getattr(getattr(original, "diag", None), "constraint_name", None)
    if constraint is not None:
        return getattr(original, "pgcode", None) == "23505" and constraint in {
            "uq_mt_exit_popup_singleton", "exit_popup_config_pkey",
        }
    return isinstance(original, sqlite3.IntegrityError) and str(original) in {
        "UNIQUE constraint failed: exit_popup_config.tenant_id",
        "UNIQUE constraint failed: exit_popup_config.id",
    }


class ExitPopupService:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create(self, tenant_id: str):
        def owned_config():
            return self.db.query(ExitPopupConfig).filter(
                ExitPopupConfig.tenant_id == tenant_id,
            ).one_or_none()

        cfg = owned_config()
        if cfg is not None:
            return cfg
        config_id = "default" if tenant_id == "default" else f"exit-popup-{tenant_id}"
        cfg = ExitPopupConfig(id=config_id, tenant_id=tenant_id)
        self.db.add(cfg)
        try:
            self.db.commit()
        except IntegrityError as error:
            self.db.rollback()
            if not _is_creation_conflict(error):
                raise
            # Another request may have inserted this tenant's singleton after
            # our read. Never recover by looking up an ID owned by another tenant.
            existing = owned_config()
            if existing is None:
                raise
            return existing
        self.db.refresh(cfg)
        return cfg

    def update(self, tenant_id: str, changes: dict):
        cfg = self.get_or_create(tenant_id)
        for field, value in changes.items():
            if field == "trigger_delay_seconds":
                value = max(1, min(int(value), 3600))
            setattr(cfg, field, value)
        cfg.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(cfg)
        return cfg
