from pathlib import Path


ROOT = Path(__file__).parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_installer_collects_validates_and_writes_admin_credentials():
    defaults = _read("installer/config/defaults.env")
    prompts = _read("installer/lib/prompts.sh")
    install = _read("installer/install.sh")
    backend = _read("installer/lib/backend.sh")

    assert "ADMIN_NAME=Administrador" in defaults
    assert "ADMIN_PASSWORD=" in defaults
    assert 'ask_required ADMIN_EMAIL "Email admin inicial"' in prompts
    assert 'ask_required ADMIN_NAME "Nome do admin inicial"' in prompts
    assert (
        'ask_required ADMIN_PASSWORD "Senha do admin inicial" '
        '"${ADMIN_PASSWORD:-}" true'
    ) in prompts
    assert 'read -r -s -p "$label: " answer' in prompts
    assert 'read -r -s -p "$label${default:+ [$default]}: " answer' not in prompts
    assert "validate_required ADMIN_PASSWORD" in install
    assert 'validate_secret_for_env ADMIN_PASSWORD "$ADMIN_PASSWORD"' in install
    assert "ADMIN_EMAIL=${ADMIN_EMAIL}" in backend
    assert "ADMIN_NAME=${ADMIN_NAME}" in backend
    assert "ADMIN_PASSWORD=${ADMIN_PASSWORD}" in backend


def test_installer_masks_admin_password_and_does_not_write_it_to_summary():
    prompts = _read("installer/lib/prompts.sh")
    validation = _read("installer/lib/validation.sh")
    summary = _read("installer/lib/summary.sh")

    assert "ADMIN_PASSWORD" in prompts
    assert '*password*|*secret*|*token*|*api_key*' in validation
    assert 'mask_value "$key" "${!key:-}"' in prompts
    assert "ADMIN_PASSWORD" not in summary
