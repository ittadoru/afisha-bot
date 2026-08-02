from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from pydantic import HttpUrl


def build_main_keyboard(mini_app_url: HttpUrl | None) -> InlineKeyboardMarkup | None:
    if mini_app_url is None:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Открыть Afisha",
                    web_app=WebAppInfo(url=str(mini_app_url)),
                )
            ]
        ]
    )
