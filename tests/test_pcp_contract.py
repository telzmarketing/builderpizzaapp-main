from datetime import date
from pathlib import Path

from backend.models.pcp import PcpWeeklyPlan
from backend.schemas.pcp import PcpPlanGenerateIn


def test_pcp_plan_is_tenant_week_unique_and_reviewable():
    assert any(c.name == "uq_pcp_weekly_plans_tenant_week" for c in PcpWeeklyPlan.__table__.constraints)
    payload = PcpPlanGenerateIn(week_start=date(2026, 10, 26), source_weeks=4)
    assert payload.source_weeks == 4
    migration = Path("backend/migrations/versions/20261026_pcp_weekly_plans.py").read_text(encoding="utf-8")
    assert "completed orders" in migration
    assert "pcp_weekly_plans" in migration
