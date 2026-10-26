"""Presence derives only from explicit storefront tab heartbeats, never analytics."""
from datetime import datetime, timedelta

from sqlalchemy import text

PRESENCE_EVENTS = ("store_presence", "store_presence_leave")


def active_storefront_visitors(db, tenant_id, now: datetime, ttl_minutes: int, public_page_filter: str):
    since = now - timedelta(minutes=max(1, min(ttl_minutes, 60)))
    rows = db.execute(text(f"""
        WITH latest_tabs AS (
            SELECT visitor_id, event_type,
                ROW_NUMBER() OVER (
                    PARTITION BY visitor_id, COALESCE(CAST(metadata_json AS JSON)->>'tab_id', session_id, visitor_id)
                    ORDER BY COALESCE(CAST(CAST(metadata_json AS JSON)->>'sequence' AS BIGINT), 0) DESC,
                             created_at DESC, id DESC
                ) AS position
            FROM visitor_events ve
            WHERE ve.tenant_id = :tenant_id AND created_at >= :online_since
              AND event_type IN ('store_presence', 'store_presence_leave')
              AND {public_page_filter}
        )
        SELECT DISTINCT visitor_id FROM latest_tabs
        WHERE position = 1 AND event_type = 'store_presence'
    """), {"tenant_id": tenant_id, "online_since": since}).scalars().all()
    return set(rows), since
