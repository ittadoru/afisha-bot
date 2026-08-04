from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock

from aiogram.types import Message
from pydantic import HttpUrl, TypeAdapter

from afishabot.bot.config import BotSettings
from afishabot.bot.handlers import HELP_TEXT, START_TEXT, handle_help, handle_start
from afishabot.bot.keyboards import build_main_keyboard


def test_main_keyboard_is_hidden_without_url() -> None:
    assert build_main_keyboard(None) is None


def test_main_keyboard_opens_mini_app() -> None:
    url = TypeAdapter(HttpUrl).validate_python("https://afisha.example/mini")

    keyboard = build_main_keyboard(url)

    assert keyboard is not None
    button = keyboard.inline_keyboard[0][0]
    assert button.text == "Открыть Afisha"
    assert button.web_app is not None
    assert button.web_app.url == "https://afisha.example/mini"


async def test_start_sends_welcome_with_mini_app_button() -> None:
    answer = AsyncMock()
    message = cast(Message, SimpleNamespace(answer=answer))
    settings = BotSettings.model_validate(
        {
            "bot_token": "123456:test-token",
            "tg_proxy_url": "http://proxy.example:8080",
            "afisha_mini_app_url": "https://afisha.example/app",
        }
    )

    await handle_start(message, settings)

    answer.assert_awaited_once_with(
        START_TEXT,
        reply_markup=build_main_keyboard(settings.afisha_mini_app_url),
    )


async def test_help_sends_command_summary() -> None:
    answer = AsyncMock()
    message = cast(Message, SimpleNamespace(answer=answer))

    await handle_help(message)

    answer.assert_awaited_once_with(HELP_TEXT)
