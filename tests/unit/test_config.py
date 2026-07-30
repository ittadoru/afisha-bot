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
