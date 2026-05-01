import json
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.database import get_db
from backend.routes.admin_auth import get_current_admin
from backend.core.response import ok

router = APIRouter(tags=["site-config"])


def _get_content(db: Session) -> dict:
    row = db.execute(text("SELECT content FROM site_config WHERE id = 'default'")).fetchone()
    if row and row[0]:
        try:
            return json.loads(row[0])
        except Exception:
            pass
    return {}


@router.get("/site-config")
def get_site_config(db: Session = Depends(get_db)):
    return ok(_get_content(db))


@router.put("/admin/site-config")
def update_site_config(
    body: dict,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    content = json.dumps(body, ensure_ascii=False)
    db.execute(text(
        "INSERT INTO site_config (id, content, updated_at) VALUES ('default', :c, NOW()) "
        "ON CONFLICT (id) DO UPDATE SET content = EXCLUDED.content, updated_at = NOW()"
    ), {"c": content})
    db.commit()
    return ok(body)
