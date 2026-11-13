from importlib.metadata import version
from pathlib import Path

from backend.core.security import hash_password, verify_password


def test_password_hash_round_trip_uses_compatible_bcrypt_pin() -> None:
    requirements = (Path(__file__).parents[1] / "backend" / "requirements.txt").read_text(
        encoding="utf-8"
    )

    assert "passlib[bcrypt]==1.7.4" in requirements
    assert "bcrypt==4.0.1" in requirements
    assert version("bcrypt") == "4.0.1"

    hashed = hash_password("local-auth-test")

    assert hashed.startswith("$2b$")
    assert verify_password("local-auth-test", hashed)
    assert not verify_password("wrong-password", hashed)
