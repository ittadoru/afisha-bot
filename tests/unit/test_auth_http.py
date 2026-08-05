from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from afishabot.app import create_app
from afishabot.core.config import Settings
from afishabot.modules.accounts.infrastructure.auth_guard import BootstrapProof


async def test_bootstrap_rejects_a_foreign_origin(settings: Settings) -> None:
    app = create_app(settings)
    app.state.redis_client = MagicMock()
    app.state.database_engine = MagicMock()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="https://podvval.xyz",
    ) as client:
        response = await client.post(
            "/auth/mini/bootstrap",
            headers={"Origin": "https://attacker.example"},
        )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "invalid_origin"


async def test_bootstrap_cookie_is_secure(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from afishabot.adapters.http import auth as auth_module

    app = create_app(settings)
    app.state.redis_client = MagicMock()
    app.state.database_engine = MagicMock()
    create = AsyncMock(return_value=BootstrapProof("nonce-value", "cookie-value"))
    monkeypatch.setattr(auth_module, "create_bootstrap", create)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="https://podvval.xyz",
    ) as client:
        response = await client.post(
            "/auth/mini/bootstrap",
            headers={"Origin": "https://podvval.xyz"},
        )

    assert response.status_code == 200
    cookie = response.headers["set-cookie"].lower()
    assert "secure" in cookie
    assert "httponly" in cookie
    assert "samesite=strict" in cookie
    assert response.headers["cache-control"] == "no-store"
