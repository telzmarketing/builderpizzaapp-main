import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text
from pydantic import ValidationError

from backend.services.storefront_presence import active_storefront_visitors
from backend.routes.marketing import VisitorEventIn, _is_public_sales_page, _public_tracking_sql


def test_presence_query_deduplicates_tabs_honors_leave_sequence_ttl_and_tenant():
    engine = create_engine("sqlite://")
    now = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE visitor_events (id TEXT, tenant_id TEXT, visitor_id TEXT, session_id TEXT, metadata_json TEXT, event_type TEXT, page TEXT, created_at TIMESTAMP)"))

        def event(id, visitor, tab, sequence, kind="store_presence", minutes=0, tenant="a", page="/"):
            connection.execute(text("INSERT INTO visitor_events VALUES (:id,:tenant,:visitor,:visitor,:meta,:kind,:page,:at)"), dict(id=id, tenant=tenant, visitor=visitor, meta=json.dumps(dict(tab_id=tab, sequence=sequence)), kind=kind, page=page, at=now-timedelta(minutes=minutes)))

        event("1", "v1", "t1", 1)
        event("2", "v1", "t2", 1)
        event("3", "v1", "t1", 2, "store_presence_leave")
        event("4", "expired", "t", 1, minutes=6)
        event("5", "internal", "t", 1, page="/painel")
        event("6", "other-tenant", "t", 1, tenant="b")
        event("7", "analytics-only", "t", 1, kind="page_view")
        # A delayed earlier heartbeat must not revive a tab that already left.
        event("8", "closed", "t", 2, "store_presence_leave", minutes=1)
        event("9", "closed", "t", 1)

        class SQLitePresenceSession:
            def execute(self, statement, parameters):
                # Only JSON extraction differs; run the production window/TTL query unchanged.
                sql = str(statement).replace("CAST(metadata_json AS JSON)->>'tab_id'", "json_extract(metadata_json, '$.tab_id')").replace("CAST(metadata_json AS JSON)->>'sequence'", "json_extract(metadata_json, '$.sequence')")
                return connection.execute(text(sql), parameters)

        active, since = active_storefront_visitors(SQLitePresenceSession(), "a", now, 5, "ve.page = '/'")
        assert active == {"v1"}
        assert since == now-timedelta(minutes=5)
        event("10", "v1", "t2", 2, "store_presence_leave")
        assert active_storefront_visitors(SQLitePresenceSession(), "a", now, 5, "ve.page = '/'")[0] == set()


@pytest.mark.parametrize("page", ["/painel", "/motoboy", "/tv/motoboys", "/painel?next=/product/1", None])
def test_internal_or_unknown_pages_are_not_positive_storefront_routes(page):
    assert not _is_public_sales_page(page)


def test_presence_metadata_is_validated_without_changing_analytics_contract():
    assert VisitorEventIn(fingerprint="v", event_type="page_view", page="/").metadata == {}
    with pytest.raises(ValidationError):
        VisitorEventIn(fingerprint="v", event_type="store_presence", page="/", metadata={"tab_id": "t", "sequence": "bad"})
    assert "SPLIT_PART" in _public_tracking_sql("ve.page")
