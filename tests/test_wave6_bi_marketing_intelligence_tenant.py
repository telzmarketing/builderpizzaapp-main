"""Security contracts for the remaining Wave 6 analytics boundaries.

BI must receive its tenant from the authenticated panel context and apply it
to every aggregate and persisted derivative.  Marketing Intelligence builds
on the same data, so goals, timeline records and every referenced entity need
the same ownership boundary.  These tests intentionally describe the target
contract before the routes are unguarded.
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _section(source: str, marker: str, next_marker: str = "\n    def ") -> str:
    start = source.index(marker)
    end = source.find(next_marker, start + len(marker))
    return source[start:end if end != -1 else None]


def test_bi_route_and_service_bind_a_trusted_panel_tenant_context():
    route = _source("backend/routes/bi.py")
    service = _source("backend/services/business_intelligence_service.py")

    assert "panel_wave6_context" in route
    assert "Depends(panel_wave6_context)" in route
    assert "wave6_tenant_id" in route
    assert "block_unsafe_wave6_route" not in route
    assert "def __init__(self, db: Session, tenant_id: str)" in service
    assert "self._tenant_id = tenant_id" in service


def test_bi_operational_aggregates_and_mobile_queries_are_tenant_scoped():
    source = _source("backend/services/business_intelligence_service.py")

    for model in ("Order", "Payment", "Customer", "OrderItem", "Product", "Delivery", "CustomerEvent", "AdDailyMetric"):
        assert f"{model}.tenant_id == self._tenant_id" in source, model

    orders = _section(source, "    def _orders_in_period(")
    paid_orders = _section(source, "    def _paid_orders_in_period(")
    online = _section(source, "    def _online_presence_counts(")
    visitors = _section(source, "    def _visitor_access_count(")
    assert "Order.tenant_id == self._tenant_id" in orders
    assert "Payment.tenant_id == self._tenant_id" in paid_orders
    assert "tenant_id = :tenant_id" in online
    assert "tenant_id = :tenant_id" in visitors
    assert '"tenant_id": self._tenant_id' in online
    assert '"tenant_id": self._tenant_id' in visitors


def test_bi_insights_and_product_performance_are_owned_per_tenant():
    source = _source("backend/services/business_intelligence_service.py")

    for method in ("_merge_persisted_insights", "_save_insights", "latest_insights", "update_insight_status"):
        section = _section(source, f"    def {method}(")
        assert "BusinessInsight.tenant_id == self._tenant_id" in section, method

    save_performance = _section(source, "    def _save_product_performance(")
    assert "ProductPerformance.tenant_id == self._tenant_id" in save_performance
    assert "tenant_id=self._tenant_id" in save_performance
    assert "tenant_id=self._tenant_id" in _section(source, "    def _save_insights(")


def test_marketing_intelligence_route_and_service_receive_the_same_tenant():
    route = _source("backend/routes/marketing_intelligence.py")
    service = _source("backend/services/marketing_intelligence_service.py")

    assert "panel_wave6_context" in route
    assert "Depends(panel_wave6_context)" in route
    assert "wave6_tenant_id" in route
    assert "block_unsafe_wave6_route" not in route
    assert "def __init__(self, db: Session, tenant_id: str)" in service
    assert "self._tenant_id = tenant_id" in service
    assert "BusinessIntelligenceService(db, tenant_id)" in service


def test_marketing_intelligence_metrics_and_references_never_cross_tenants():
    source = _source("backend/services/marketing_intelligence_service.py")

    for model in (
        "Order", "Payment", "Customer", "Campaign", "Coupon", "CouponUsage",
        "Product", "TrafficCampaign", "CampaignLink", "TrackingSession",
        "TrackingEvent", "AdDailyMetric", "CustomerEvent",
    ):
        assert f"{model}.tenant_id == self._tenant_id" in source, model

    # A caller may provide IDs for goals or timeline references, but the
    # service must prove each reference belongs to this tenant before writing.
    assert "def _validate_reference_ownership(" in source
    validation = _section(source, "    def _validate_reference_ownership(")
    assert "tenant_id == self._tenant_id" in validation
    for method in ("create_goal", "update_goal", "create_timeline_event", "update_timeline_event"):
        assert "_validate_reference_ownership" in _section(source, f"    def {method}("), method


def test_goals_timeline_and_planning_are_tenant_owned_and_fail_closed_on_foreign_ids():
    source = _source("backend/services/marketing_intelligence_service.py")

    for method in ("list_goals", "_get_goal", "list_timeline", "_get_timeline_event"):
        section = _section(source, f"    def {method}(")
        model = "MarketingGoal" if "goal" in method else "MarketingTimelineEvent"
        assert f"{model}.tenant_id == self._tenant_id" in section, method

    assert "tenant_id=self._tenant_id" in _section(source, "    def create_goal(")
    assert "tenant_id=self._tenant_id" in _section(source, "    def create_timeline_event(")
