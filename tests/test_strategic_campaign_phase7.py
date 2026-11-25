from backend.schemas.strategic_campaign import StrategicMarketingConfig
from backend.services.strategic_campaign_metrics_service import StrategicCampaignMetricsService


def test_marketing_config_accepts_planned_budget_and_attribution_source():
    config = StrategicMarketingConfig(planned_budget=1500.00, traffic_campaign_id="tc-1")
    assert config.planned_budget == 1500.00
    assert config.attribution_window_days == 30


def test_metrics_metadata_is_fail_closed_for_invalid_payloads():
    assert StrategicCampaignMetricsService._metadata('{"campaign_id":"sc-1"}') == {"campaign_id": "sc-1"}
    assert StrategicCampaignMetricsService._metadata("not-json") == {}
    assert StrategicCampaignMetricsService._metadata(None) == {}
