from backend.services.tenant_auth_service import TenantAuthSelection, choose_login_selection

def selection(tenant_id, default=False):
    return TenantAuthSelection(tenant_id, f"membership-{tenant_id}", "owner", tenant_id, tenant_id, default)

def test_single_membership_is_selected():
    assert choose_login_selection([selection("tenant-a")]).tenant_id == "tenant-a"

def test_explicit_default_is_selected():
    assert choose_login_selection([selection("tenant-a"), selection("tenant-b", True)]).tenant_id == "tenant-b"

def test_multiple_memberships_are_not_guessed():
    assert choose_login_selection([selection("tenant-a"), selection("tenant-b")]) is None

def test_claims_do_not_infer_platform_role():
    assert "platform_role" not in selection("tenant-a").claims()
