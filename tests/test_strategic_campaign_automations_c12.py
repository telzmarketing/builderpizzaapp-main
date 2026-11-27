from backend.schemas.strategic_campaign_automation import StrategicCampaignAutomationUpdate
from backend.services.strategic_campaign_automation_service import StrategicCampaignAutomationService


def test_catalog_is_derived_from_commercial_settings():
    base = StrategicCampaignAutomationService._catalog({})
    scheduled = StrategicCampaignAutomationService._catalog({"require_scheduled_order": True})
    preorder = StrategicCampaignAutomationService._catalog({"sales_mode": "preorder"})

    assert [item["automation_key"] for item in base] == [
        "order_confirmation", "payment_confirmation",
    ]
    assert "schedule_confirmation" in {item["automation_key"] for item in scheduled}
    assert "schedule_reminder" in {item["automation_key"] for item in scheduled}
    assert "reservation_created" in {item["automation_key"] for item in preorder}


def test_commercial_config_fingerprint_is_order_independent():
    left = StrategicCampaignAutomationService._fingerprint({"sales_mode": "preorder", "min_lead_minutes": 30})
    right = StrategicCampaignAutomationService._fingerprint({"min_lead_minutes": 30, "sales_mode": "preorder"})
    changed = StrategicCampaignAutomationService._fingerprint({"sales_mode": "immediate", "min_lead_minutes": 30})

    assert left == right
    assert left != changed


def test_update_contract_only_allows_definition_and_enabled():
    payload = StrategicCampaignAutomationUpdate(enabled=False, definition={"actions": []})
    assert payload.model_dump() == {"enabled": False, "definition": {"actions": []}}
