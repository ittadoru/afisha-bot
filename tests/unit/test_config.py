from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from afishabot.core.config import Environment, Settings


def test_settings_mask_connection_strings(tmp_path: Path) -> None:
    settings = Settings(
        environment=Environment.TEST,
        database_url=SecretStr("postgresql+asyncpg://user:password@db/test"),
        redis_url=SecretStr("redis://:password@redis/0"),
        media_root=tmp_path,
    )

    assert "password" not in repr(settings)
    assert settings.database_dsn().endswith("@db/test")


def test_unknown_constructor_field_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(unknown_secret="must-not-be-accepted")  # type: ignore[call-arg]


def test_stage_a_public_urls_are_https() -> None:
    settings = Settings()

    assert str(settings.public_base_url) == "https://podvval.xyz/"
    assert str(settings.admin_base_url) == "https://admin.podvval.xyz/"


def test_public_urls_reject_plain_http() -> None:
    with pytest.raises(ValidationError, match="must use HTTPS"):
        Settings(public_base_url="http://podvval.xyz")  # type: ignore[arg-type]
