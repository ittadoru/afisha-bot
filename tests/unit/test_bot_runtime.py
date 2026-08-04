from types import SimpleNamespace
from typing import ClassVar

import pytest

from afishabot.bot import runtime
from afishabot.bot.config import BotSettings


class FakeSession:
    last_proxy: ClassVar[str | None] = None
    closed: ClassVar[bool] = False

    def __init__(self, proxy: str | None = None) -> None:
        type(self).last_proxy = proxy
        type(self).closed = False

    async def close(self) -> None:
        type(self).closed = True


class FakeBot:
    fail_get_me: ClassVar[bool] = False

    def __init__(self, token: str, session: FakeSession) -> None:
        self.token = token
        self.session = session

    async def get_me(self) -> object:
        if self.fail_get_me:
            raise RuntimeError("telegram unavailable")
        return SimpleNamespace(id=123, username="afisha_test_bot")

    async def delete_webhook(self, *, drop_pending_updates: bool) -> None:
        assert drop_pending_updates is False


class FakeDispatcher:
    polling_started: ClassVar[bool] = False

    def include_router(self, router: object) -> None:
        del router

    def resolve_used_update_types(self) -> list[str]:
        return ["message"]

    async def start_polling(self, bot: object, **kwargs: object) -> None:
        del bot
        assert kwargs["allowed_updates"] == ["message"]
        type(self).polling_started = True


def settings() -> BotSettings:
    return BotSettings.model_validate(
        {
            "bot_token": "123456:test-token",
            "tg_proxy_url": "http://proxy.example:8080",
        }
    )


def install_fakes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runtime, "AiohttpSession", FakeSession)
    monkeypatch.setattr(runtime, "Bot", FakeBot)
    monkeypatch.setattr(runtime, "Dispatcher", FakeDispatcher)


async def test_check_only_probes_proxy_and_closes_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_fakes(monkeypatch)

    await runtime.run_polling(settings(), check_only=True)

    assert FakeSession.last_proxy == "http://proxy.example:8080"
    assert FakeSession.closed is True
    assert FakeDispatcher.polling_started is False


async def test_check_only_uses_direct_connection_without_proxy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_fakes(monkeypatch)
    direct_settings = BotSettings.model_validate({"bot_token": "123456:test-token"})

    await runtime.run_polling(direct_settings, check_only=True)

    assert FakeSession.last_proxy is None
    assert FakeSession.closed is True


async def test_polling_starts_and_closes_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_fakes(monkeypatch)
    FakeDispatcher.polling_started = False

    await runtime.run_polling(settings())

    assert FakeDispatcher.polling_started is True
    assert FakeSession.closed is True


async def test_probe_failure_still_closes_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_fakes(monkeypatch)
    FakeBot.fail_get_me = True
    try:
        with pytest.raises(RuntimeError, match="telegram unavailable"):
            await runtime.run_polling(settings(), check_only=True)
        assert FakeSession.closed is True
    finally:
        FakeBot.fail_get_me = False
