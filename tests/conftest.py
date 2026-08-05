from collections.abc import Iterator
from pathlib import Path

import pytest

from afishabot.core.config import Environment, Settings


@pytest.fixture
def settings(tmp_path: Path) -> Iterator[Settings]:
    yield Settings.model_validate(
        {
            "environment": Environment.TEST,
            "database_url": "postgresql+asyncpg://test:test@postgres:5432/test",
            "redis_url": "redis://redis:6379/15",
            "media_root": tmp_path / "media",
            "BOT_TOKEN": "123456:test-token",
            "auth_hmac_secret": "test-auth-secret-that-is-long-enough-123456",
        }
    )
