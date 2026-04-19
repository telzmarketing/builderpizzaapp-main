from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.routes.admin_auth import get_current_admin
from backend.core.response import ok
from backend.database import get_db
from backend.models.theme import ThemeSettings
from backend.schemas.theme import ThemeSettingsOut, ThemeSettingsUpdate

router = APIRouter(prefix="/theme", tags=["theme"])

_DEFAULTS = {
    "id": "default",
    "primary": "#f97316",
    "secondary": "#2d3d56",
    "background_main": "#0c1220",
    "background_alt": "#111827",
    "background_card": "#1e2a3b",
    "text_primary": "#f8fafc",
    "text_secondary": "#e2e8f0",
    "text_muted": "#94a3b8",
    "status_success": "#22c55e",
    "status_error": "#ef4444",
    "status_warning": "#f59e0b",
    "status_info": "#3b82f6",
    "border": "#2d3d56",
    "interaction_hover": "#fb923c",
    "interaction_active": "#ea6f10",
    "interaction_focus": "#f97316",
    "navbar": "#111827",
    "footer": "#0c1220",
    "sidebar": "#111827",
    "modal": "#1e2a3b",
    "overlay": "#000000",
    "badge": "#f97316",
    "tag": "#2d3d56",
}


def _get_or_create(db: Session) -> ThemeSettings:
    row = db.get(ThemeSettings, "default")
    if row is None:
        row = ThemeSettings(**_DEFAULTS)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


@router.get("", response_model=ThemeSettingsOut)
def get_theme(db: Session = Depends(get_db)):
    return ok(ThemeSettingsOut.model_validate(_get_or_create(db)))


@router.put("", response_model=ThemeSettingsOut)
def update_theme(
    body: ThemeSettingsUpdate,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    row = _get_or_create(db)
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(row, field, val)
    db.commit()
    db.refresh(row)
    return ok(ThemeSettingsOut.model_validate(row))
