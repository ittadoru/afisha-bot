import asyncio
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from anyio import to_thread
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

STAGED_EVENT_PHOTO_TTL = timedelta(hours=24)
MEDIA_CLEANUP_INTERVAL_SECONDS = 60 * 60

logger = logging.getLogger(__name__)


def event_photo_path(media_root: Path, asset_id: UUID) -> Path:
    return media_root / "event-staging" / f"{asset_id}.webp"


async def cleanup_expired_event_photos(engine: AsyncEngine, media_root: Path) -> int:
    """Claim expired, unattached uploads and remove their files."""
    async with engine.begin() as connection:
        rows = (
            await connection.execute(
                text(
                    """
                    WITH expired AS (
                        SELECT a.id
                        FROM media.assets a
                        WHERE a.purpose = 'event_photo'
                          AND a.state = 'ready'
                          AND a.delete_after <= now()
                          AND NOT EXISTS (
                              SELECT 1 FROM events.event_photos ep
                              WHERE ep.media_asset_id = a.id
                          )
                        FOR UPDATE SKIP LOCKED
                    )
                    UPDATE media.assets a
                    SET state = 'deleted', updated_at = now()
                    FROM expired
                    WHERE a.id = expired.id
                    RETURNING expired.id
                    """
                )
            )
        ).scalars().all()

    for asset_id in rows:
        await to_thread.run_sync(event_photo_path(media_root, asset_id).unlink, True)
    return len(rows)


async def event_photo_cleanup_loop(engine: AsyncEngine, media_root: Path) -> None:
    while True:
        await asyncio.sleep(MEDIA_CLEANUP_INTERVAL_SECONDS)
        try:
            removed = await cleanup_expired_event_photos(engine, media_root)
            if removed:
                logger.info("Expired temporary event photos removed count=%d", removed)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Temporary event photo cleanup failed")


def expires_at() -> datetime:
    return datetime.now(UTC) + STAGED_EVENT_PHOTO_TTL
