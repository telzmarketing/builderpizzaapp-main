"""Regression coverage for the shared CRM customer-group model."""


def test_marketing_route_uses_the_shared_customer_group_model():
    from backend.models.crm import CustomerGroup
    from backend.routes import marketing

    assert marketing.CustomerGroup is CustomerGroup


def test_application_imports_with_marketing_routes_registered():
    from backend.main import app

    assert app is not None
