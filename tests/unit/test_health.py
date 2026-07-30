from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from afishabot.adapters.http import health
from afishabot.app import create_app
from afishabot.core.config import Settings


async def test_readiness_is_generic_when_database_is_unready(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(settings)
    app.state.database_engine = object()
    monkeypatch.setattr(health, "database_is_ready", AsyncMock(return_value=False))
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
    assert "database" not in response.text.lower()


async def test_readiness_opens_only_for_current_database(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(settings)
    app.state.database_engine = object()
    monkeypatch.setattr(health, "database_is_ready", AsyncMock(return_value=True))
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
