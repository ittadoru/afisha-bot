from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from afishabot.bot.config import BotSettings
from afishabot.bot.keyboards import build_main_keyboard

START_TEXT = (
    "Добро пожаловать в Afisha! 👋\n\n"
    "Здесь можно будет находить бесплатные офлайн-события рядом, "
    "знакомиться с людьми и участвовать в городской жизни."  # noqa: RUF001
)
HELP_TEXT = (
    "Доступные команды:\n"
    "/start — открыть приветствие Afisha\n"
    "/help — показать эту справку\n\n"
    "Основная работа происходит в Mini App."
)

router = Router(name="afisha-mvp-bot")


@router.message(CommandStart())
async def handle_start(message: Message, settings: BotSettings) -> None:
    await message.answer(
        START_TEXT,
        reply_markup=build_main_keyboard(settings.afisha_mini_app_url),
    )


@router.message(Command("help"))
async def handle_help(message: Message) -> None:
    await message.answer(HELP_TEXT)
