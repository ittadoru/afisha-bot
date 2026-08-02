import pytest
from pydantic import ValidationError

from afishabot.bot.config import BotSettings


def test_bot_settings_require_token_and_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    monkeypatch.delenv("TG_PROXY_URL", raising=False)

    with pytest.raises(ValidationError):
        BotSettings.model_validate({})


def test_bot_settings_hide_secrets() -> None:
    settings = BotSettings.model_validate(
        {
            "bot_token": "123456:test-token",
            "tg_proxy_url": "http://proxy.example:8080",
        }
    )

    rendered = repr(settings)

    assert "test-token" not in rendered
    assert "proxy.example" not in rendered
    assert settings.token() == "123456:test-token"


def test_bot_settings_reject_empty_proxy() -> None:
    settings = BotSettings.model_validate(
        {"bot_token": "123456:test-token", "tg_proxy_url": ""}
    )

    with pytest.raises(ValueError, match="must not be empty"):
        settings.validated()


def test_mini_app_url_must_use_https() -> None:
    with pytest.raises(ValidationError, match="must use HTTPS"):
        BotSettings.model_validate(
            {
                "bot_token": "123456:test-token",
                "tg_proxy_url": "http://proxy.example:8080",
                "afisha_mini_app_url": "http://app.example",
            }
        )
