from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from afishabot.app import create_app
from afishabot.core.config import Settings


async def test_factory_creates_independent_instances(settings: Settings) -> None:
    first = create_app(settings)
    second = create_app(settings)

    assert first is not second
    assert first.state is not second.state


async def test_liveness_does_not_require_dependencies(settings: Settings) -> None:
    app = create_app(settings)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "x-request-id" in response.headers


async def test_request_id_rejects_untrusted_text(settings: Settings) -> None:
    app = create_app(settings)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/health/live",
            headers={"X-Request-ID": "secret-or-arbitrary-user-text"},
        )

    assert response.headers["x-request-id"] != "secret-or-arbitrary-user-text"


async def test_valid_request_id_is_preserved(settings: Settings) -> None:
    app = create_app(settings)
    transport = ASGITransport(app=app)
    request_id = str(uuid4())

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/health/live",
            headers={"X-Request-ID": request_id},
        )

    assert response.headers["x-request-id"] == request_id
