from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_backend_routes_and_services_have_no_mojibake_markers():
    files = [
        ROOT / "backend/routes/promotions.py",
        ROOT / "backend/routes/crm.py",
        ROOT / "backend/routes/shipping.py",
        ROOT / "backend/services/shipping_service.py",
    ]
    mojibake_markers = ("Ã£", "Ã§", "Ã¢", "Ã©", "Ã³", "Ãº", "Ãª", "Ã¡", "Ãµ", "Â", "�")

    for path in files:
        text = path.read_text(encoding="utf-8")
        assert not any(marker in text for marker in mojibake_markers), path
