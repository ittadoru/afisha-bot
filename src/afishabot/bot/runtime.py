import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession

from afishabot.bot.config import BotSettings, load_bot_settings
from afishabot.bot.handlers import router
from afishabot.core.logging import configure_logging

logger = logging.getLogger("afishabot.bot")


async def run_polling(
    settings: BotSettings | None = None,
    *,
    check_only: bool = False,
) -> None:
    config = (settings or load_bot_settings()).validated()
    session = AiohttpSession(proxy=config.proxy_url())
    bot = Bot(token=config.token(), session=session)
    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    try:
        identity = await bot.get_me()
        logger.info(
            "Telegram Bot API check passed bot_id=%s username=%s proxy_enabled=true",
            identity.id,
            identity.username,
        )
        if check_only:
            return

        await bot.delete_webhook(drop_pending_updates=False)
        logger.info("Starting Telegram polling proxy_enabled=true")
        await dispatcher.start_polling(  # pyright: ignore[reportUnknownMemberType]
            bot,
            settings=config,
            allowed_updates=dispatcher.resolve_used_update_types(),
        )
    finally:
        await bot.session.close()


def main() -> None:
    settings = load_bot_settings().validated()
    configure_logging(settings.afisha_log_level)
    asyncio.run(run_polling(settings))
