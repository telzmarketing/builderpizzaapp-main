from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_public_kit_id_route_uses_tenant_scoped_service_lookup():
    route = (ROOT / "backend/routes/campaigns.py").read_text(encoding="utf-8")

    assert '@router.get("/kits/id/{kit_id}", response_model=PromotionalKitOut)' in route
    assert "resolve_public_tenant_context(request, db)" in route
    assert ".get_public_kit_by_id(kit_id)" in route


def test_public_kit_id_lookup_preserves_active_and_expiration_guards():
    service = (ROOT / "backend/services/campaign_service.py").read_text(encoding="utf-8")
    method = service.split("    def get_public_kit_by_id", 1)[1].split("    def _unique_kit_slug", 1)[0]

    assert "kit = self.get_kit(kit_id)" in method
    assert "if not kit or not kit.active:" in method
    assert "kit.valid_until" in method
