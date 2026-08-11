import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

from anyio import to_thread
from fastapi import APIRouter, Cookie, Header, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import text

from afishabot.adapters.http.auth import CSRF_HEADER, SESSION_COOKIE
from afishabot.adapters.http.profiles import (
    current_user,
    dependencies,
    mutation_user,
    validate_origin,
)
from afishabot.modules.media.application.image_processing import (
    EventImageProcessor,
    NormalizedCrop,
    UnsafeImageError,
)
from afishabot.modules.media.application.staged_event_photos import (
    event_photo_path,
    expires_at,
)

router = APIRouter(prefix="/media", tags=["media"])
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_UPLOAD_BYTES = 12 * 1024 * 1024

logger = logging.getLogger(__name__)


class EventPhotoResponse(BaseModel):
    upload_id: UUID
    preview_url: str
    expires_at: datetime
    width: int = 1200
    height: int = 900


@router.put("/event-photo", response_model=EventPhotoResponse, status_code=201)
async def upload_event_photo(
    request: Request,
    crop_x: Annotated[float | None, Header(alias="X-Afisha-Crop-X")] = None,
    crop_y: Annotated[float | None, Header(alias="X-Afisha-Crop-Y")] = None,
    crop_width: Annotated[float | None, Header(alias="X-Afisha-Crop-Width")] = None,
    crop_height: Annotated[float | None, Header(alias="X-Afisha-Crop-Height")] = None,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    csrf: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
) -> EventPhotoResponse:
    settings, _, engine = dependencies(request)
    validate_origin(request, settings)
    user_id = await mutation_user(request, token, csrf)
    content_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=415, detail="unsupported_image")

    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="image_too_large")
    if not data:
        raise HTTPException(status_code=422, detail="empty_image")

    asset_id = uuid4()
    source = settings.media_root / "quarantine" / f"{asset_id}.upload"
    destination = event_photo_path(settings.media_root, asset_id)
    card = destination.with_name(f"{asset_id}.640.webp")
    thumbnail = destination.with_name(f"{asset_id}.320.webp")
    await to_thread.run_sync(source.parent.mkdir, 0o750, True, True)
    await to_thread.run_sync(source.write_bytes, bytes(data))
    try:
        crop = None
        if (
            crop_x is not None
            and crop_y is not None
            and crop_width is not None
            and crop_height is not None
        ):
            crop = NormalizedCrop(crop_x, crop_y, crop_width, crop_height)
        await to_thread.run_sync(
            EventImageProcessor().process_variants,
            source,
            destination,
            card,
            thumbnail,
            crop,
        )
    except UnsafeImageError as error:
        for path in (destination, card, thumbnail):
            await to_thread.run_sync(path.unlink, True)
        logger.warning(
            "event_photo_rejected user=%s reason=%s "
            "crop_x=%s crop_y=%s crop_width=%s crop_height=%s",
            user_id,
            error,
            crop_x,
            crop_y,
            crop_width,
            crop_height,
        )
        raise HTTPException(status_code=422, detail=str(error)) from error

    checksum = await to_thread.run_sync(
        lambda: hashlib.sha256(destination.read_bytes()).hexdigest()
    )
    card_checksum = await to_thread.run_sync(
        lambda: hashlib.sha256(card.read_bytes()).hexdigest()
    )
    thumbnail_checksum = await to_thread.run_sync(
        lambda: hashlib.sha256(thumbnail.read_bytes()).hexdigest()
    )
    expiry = expires_at()
    old_paths: list[Path] = []
    try:
        async with engine.begin() as connection:
            previous = (
                (
                    await connection.execute(
                        text(
                            """
                        SELECT a.id, a.storage_key
                        FROM media.assets a
                        WHERE a.owner_user_id = :user
                          AND a.purpose = 'event_photo'
                          AND a.state = 'ready'
                          AND NOT EXISTS (
                              SELECT 1 FROM events.event_photos ep
                              WHERE ep.media_asset_id = a.id
                          )
                        FOR UPDATE
                        """
                        ),
                        {"user": user_id},
                    )
                )
                .mappings()
                .all()
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO media.assets
                        (id, owner_user_id, purpose, state, storage_key, mime_type,
                         byte_size, width, height, checksum_sha256, delete_after)
                    VALUES
                        (:id, :user, 'event_photo', 'ready', :key, 'image/webp',
                         :size, 1200, 900, :checksum, :delete_after)
                    """
                ),
                {
                    "id": asset_id,
                    "user": user_id,
                    "key": f"event-staging/{asset_id}.webp",
                    "size": destination.stat().st_size,
                    "checksum": checksum,
                    "delete_after": expiry,
                },
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO media.asset_variants
                      (id,source_asset_id,variant_key,storage_key,mime_type,
                       width,height,byte_size,checksum_sha256)
                    VALUES
                      (:card_id,:asset,'event_640',:card_key,'image/webp',
                       640,480,:card_size,:card_checksum),
                      (:thumb_id,:asset,'event_320',:thumb_key,'image/webp',
                       320,240,:thumb_size,:thumb_checksum)
                    """
                ),
                {
                    "card_id": uuid4(),
                    "thumb_id": uuid4(),
                    "asset": asset_id,
                    "card_key": f"event-staging/{asset_id}.640.webp",
                    "thumb_key": f"event-staging/{asset_id}.320.webp",
                    "card_size": card.stat().st_size,
                    "thumb_size": thumbnail.stat().st_size,
                    "card_checksum": card_checksum,
                    "thumb_checksum": thumbnail_checksum,
                },
            )
            for previous_asset in previous:
                keys = (
                    (
                        await connection.execute(
                            text(
                                """SELECT storage_key FROM media.assets WHERE id=:id
                                UNION SELECT storage_key FROM media.asset_variants
                                WHERE source_asset_id=:id"""
                            ),
                            {"id": previous_asset["id"]},
                        )
                    )
                    .scalars()
                    .all()
                )
                old_paths.extend(settings.media_root / key for key in set(keys))
                await connection.execute(
                    text("DELETE FROM media.asset_variants WHERE source_asset_id=:id"),
                    {"id": previous_asset["id"]},
                )
                await connection.execute(
                    text(
                        "UPDATE media.assets SET state='deleted', updated_at=now() "
                        "WHERE id=:id"
                    ),
                    {"id": previous_asset["id"]},
                )
    except Exception:
        await to_thread.run_sync(destination.unlink, True)
        await to_thread.run_sync(card.unlink, True)
        await to_thread.run_sync(thumbnail.unlink, True)
        raise

    for old_path in old_paths:
        await to_thread.run_sync(old_path.unlink, True)
    return EventPhotoResponse(
        upload_id=asset_id,
        preview_url=f"/api/media/event-photos/{asset_id}",
        expires_at=expiry,
    )


@router.get("/event-photos/{upload_id}")
async def event_photo_preview(
    upload_id: UUID,
    request: Request,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> Response:
    settings, _, engine = dependencies(request)
    user_id = await current_user(request, token)
    async with engine.connect() as connection:
        exists = await connection.scalar(
            text(
                """
                SELECT 1 FROM media.assets
                WHERE id=:id AND owner_user_id=:user AND purpose='event_photo'
                  AND state='ready' AND delete_after > now()
                """
            ),
            {"id": upload_id, "user": user_id},
        )
    path = event_photo_path(settings.media_root, upload_id)
    if exists is None or not path.is_file():
        raise HTTPException(status_code=404, detail="event_photo_not_found")
    return FileResponse(
        path,
        media_type="image/webp",
        headers={"Cache-Control": "private, no-store"},
    )


@router.delete("/event-photos/{upload_id}", status_code=204)
async def delete_event_photo(
    upload_id: UUID,
    request: Request,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    csrf: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
) -> Response:
    settings, _, engine = dependencies(request)
    validate_origin(request, settings)
    user_id = await mutation_user(request, token, csrf)
    paths: list[Path] = []
    async with engine.begin() as connection:
        keys = (
            (
                await connection.execute(
                    text(
                        """
                        SELECT storage_key FROM media.assets WHERE id=:id
                        UNION
                        SELECT storage_key FROM media.asset_variants
                        WHERE source_asset_id=:id
                        """
                    ),
                    {"id": upload_id},
                )
            )
            .scalars()
            .all()
        )
        paths = [settings.media_root / key for key in set(keys)]
        deleted = await connection.scalar(
            text(
                """
                UPDATE media.assets a SET state='deleted', updated_at=now()
                WHERE a.id=:id AND a.owner_user_id=:user
                  AND a.purpose='event_photo' AND a.state='ready'
                  AND NOT EXISTS (
                      SELECT 1 FROM events.event_photos ep
                      WHERE ep.media_asset_id=a.id
                  )
                RETURNING 1
                """
            ),
            {"id": upload_id, "user": user_id},
        )
        if deleted is None:
            raise HTTPException(status_code=404, detail="event_photo_not_found")
        await connection.execute(
            text("DELETE FROM media.asset_variants WHERE source_asset_id=:id"),
            {"id": upload_id},
        )
    for path in paths:
        await to_thread.run_sync(path.unlink, True)
    return Response(status_code=204)
