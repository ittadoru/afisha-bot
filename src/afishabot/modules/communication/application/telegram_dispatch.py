"""Push in-app notifications to their recipients over Telegram."""

import logging
from collections import defaultdict
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramForbiddenError,
    TelegramUnauthorizedError,
)
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from afishabot.bot.config import BotSettings

LOG = logging.getLogger(__name__)

KIND_ICONS: dict[str, str] = {
    "event_cancelled": "🚫",
    "event_participation_excluded": "↩️",
    "waitlist_promoted": "✨",
    "event_approved": "✅",
    "event_rejected": "⛔",
    "event_changed": "🔁",
    "looking_post.question": "💬",
    "looking_post.answer": "💬",
}

FETCH_BATCH = 200
MAX_PER_RECIPIENT = 5


async def _fetch_pending(engine: AsyncEngine) -> list[dict[str, Any]]:
    async with engine.connect() as connection:
        rows = (
            (
                await connection.execute(
                    text(
                        """
                    SELECT n.id, n.kind, n.title, n.body, n.deep_link,
                           n.recipient_user_id, t.telegram_user_id
                    FROM communication.notifications n
                    JOIN accounts.telegram_identities t
                      ON t.user_id = n.recipient_user_id
                    WHERE n.tg_pushed_at IS NULL
                      AND n.delivery_policy = 'telegram_and_in_app'
                      AND n.telegram_status = 'pending'
                      AND n.created_at <= now() - interval '3 seconds'
                    ORDER BY n.created_at, n.id
                    LIMIT :limit
                    """
                    ),
                    {"limit": FETCH_BATCH},
                )
            )
            .mappings()
            .all()
        )
    return [dict(row) for row in rows]


async def _mark_delivery(
    engine: AsyncEngine, ids: list[Any], *, status: str
) -> None:
    if not ids:
        return
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "UPDATE communication.notifications "
                "SET tg_pushed_at = now(), telegram_status = :status, "
                "telegram_last_attempt_at = now(), "
                "telegram_sent_at = CASE WHEN :status = 'sent' THEN now() "
                "ELSE telegram_sent_at END "
                "WHERE id = ANY(:ids)"
            ),
            {"ids": ids, "status": status},
        )


def _compose_text(items: list[dict[str, Any]]) -> str:
    return "\n\n".join(
        f"{KIND_ICONS.get(item['kind'], '📣')} {item['title']}\n{item['body']}"
        for item in items
    )


def _safe_web_app_url(
    bot_settings: BotSettings, deep_link: str | None = None
) -> str | None:
    base_url = bot_settings.afisha_mini_app_url
    if base_url is None:
        return None
    base = urlsplit(str(base_url))
    if base.scheme not in {"https"} or not base.netloc:
        return None
    path = deep_link or "/app"
    parsed = urlsplit(path)
    if parsed.scheme or parsed.netloc or not parsed.path.startswith("/app"):
        path = "/app"
        parsed = urlsplit(path)
    return urlunsplit((base.scheme, base.netloc, parsed.path, parsed.query, ""))


def _open_button(
    bot_settings: BotSettings, deep_link: str | None = None
) -> InlineKeyboardMarkup | None:
    url = _safe_web_app_url(bot_settings, deep_link)
    if url is None:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Открыть в Afisha", web_app=WebAppInfo(url=url))]
        ]
    )


async def dispatch_telegram_notifications(engine: AsyncEngine) -> int:
    """Send one round of queued notifications to their Telegram recipients."""
    bot_settings = BotSettings()  # pyright: ignore[reportCallIssue]
    session = AiohttpSession(proxy=bot_settings.proxy_url())
    bot = Bot(token=bot_settings.token(), session=session)
    try:
        pending = await _fetch_pending(engine)
        if not pending:
            return 0
        grouped: dict[tuple[Any, Any], list[dict[str, Any]]] = defaultdict(list)
        for item in pending:
            grouped[(item["recipient_user_id"], item["telegram_user_id"])].append(item)

        sent: list[Any] = []
        doomed: list[Any] = []
        for (recipient_user_id, telegram_user_id), items in grouped.items():
            batch = items[:MAX_PER_RECIPIENT]
            try:
                await bot.send_message(
                    chat_id=telegram_user_id,
                    text=_compose_text(batch),
                    reply_markup=_open_button(bot_settings, batch[0].get("deep_link")),
                )
                sent.extend(item["id"] for item in batch)
            except TelegramForbiddenError, TelegramUnauthorizedError:
                # The user never started the bot (or blocked it). End the
                # notification's life to avoid hammering the API forever.
                doomed.extend(item["id"] for item in batch)
                LOG.info(
                    "Telegram push unreachable for user %s (%d items)",
                    recipient_user_id,
                    len(batch),
                )
            except TelegramAPIError as exc:
                # Transient failures (5xx, flood control) stay queued for the
                # next sweep.
                LOG.warning("Telegram push to %s failed: %s", recipient_user_id, exc)
        await _mark_delivery(engine, sent, status="sent")
        await _mark_delivery(engine, doomed, status="unreachable")
        return len(sent) + len(doomed)
    finally:
        await bot.session.close()
