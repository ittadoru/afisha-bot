from unittest.mock import AsyncMock, MagicMock

import pytest

from afishabot.app import create_app
from afishabot.core import lifespan as lifespan_module
from afishabot.core.config import Settings


async def test_lifespan_owns_dependency_cleanup(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = MagicMock()
    engine.dispose = AsyncMock()
    redis_client = MagicMock()
    redis_client.aclose = AsyncMock()
    monkeypatch.setattr(
        lifespan_module,
        "create_database_engine",
        MagicMock(return_value=engine),
    )
    monkeypatch.setattr(
        lifespan_module,
        "create_redis_client",
        MagicMock(return_value=redis_client),
    )
    monkeypatch.setattr(
        lifespan_module,
        "redis_is_available",
        AsyncMock(return_value=False),
    )
    bootstrap = AsyncMock()
    monkeypatch.setattr(lifespan_module, "bootstrap_first_admin", bootstrap)
    app = create_app(settings)

    async with lifespan_module.lifespan(app):
        assert app.state.database_engine is engine
        assert app.state.redis_client is redis_client
        assert settings.media_root.exists()

    engine.dispose.assert_awaited_once()
    redis_client.aclose.assert_awaited_once()
    bootstrap.assert_awaited_once()
