import hashlib
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal, cast
from uuid import UUID, uuid4

from anyio import to_thread
from fastapi import APIRouter, Cookie, Header, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from afishabot.adapters.http.auth import CSRF_HEADER, SESSION_COOKIE
from afishabot.core.config import Settings
from afishabot.modules.accounts.application.profiles import (
    ProfileConflict,
    ProfileError,
    ProfileNotFound,
    ProfileView,
    account_events,
    create_report,
    load_profile,
    profile_events,
    session_user_id,
    update_profile,
    update_profile_city,
)
from afishabot.modules.media.application.image_processing import (
    AvatarImageProcessor,
    UnsafeImageError,
)

router = APIRouter(tags=["profiles"])


class OwnProfileResponse(BaseModel):
    public_id: str
    display_name: str
    bio: str | None
    selected_city_id: str | None
    city_name: str | None
    avatar_url: str | None
    version: int
    next_name_change_at: str | None
    organizer_status: str
    successful_events: int
    upcoming_count: int
    completed_count: int
    age_confirmed: bool = True


class PublicProfileResponse(BaseModel):
    public_id: str
    display_name: str
    bio: str | None
    avatar_url: str | None
    organizer_status: str
    successful_events: int


class UpdateProfileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str
    bio: str | None = None
    selected_city_id: UUID
    version: int = Field(gt=0)


class UpdateProfileCityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    selected_city_id: UUID
    version: int = Field(gt=0)


class ReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: Literal["photo", "display_name", "bio", "other"]
    comment: str | None = Field(default=None, max_length=300)


class EventResponse(BaseModel):
    id: UUID
    title: str
    starts_at: datetime
    ends_at: datetime
    category: str
    role: str | None = None


class AnonymousPublicProfileResponse(PublicProfileResponse):
    upcoming_events: list[EventResponse]


class EventsResponse(BaseModel):
    items: list[EventResponse]
    next_offset: int | None


class NotificationResponse(BaseModel):
    id: UUID
    kind: str
    importance: str
    title: str
    body: str
    deep_link: str | None
    created_at: datetime
    read_at: datetime | None


def dependencies(request: Request) -> tuple[Settings, Redis, AsyncEngine]:
    return (
        cast(Settings, request.app.state.settings),
        cast(Redis, request.app.state.redis_client),
        cast(AsyncEngine, request.app.state.database_engine),
    )


def auth_secret(settings: Settings) -> bytes:
    value = settings.auth_secret()
    if value is None:
        raise HTTPException(status_code=503, detail="profile_unavailable")
    return value


def validate_origin(request: Request, settings: Settings) -> None:
    if request.headers.get("Origin") != str(settings.public_base_url).rstrip("/"):
        raise HTTPException(status_code=403, detail="invalid_origin")


async def current_user(
    request: Request, token: str | None, csrf: str | None = None
) -> UUID:
    if token is None:
        raise HTTPException(status_code=401, detail="session_required")
    settings, _, engine = dependencies(request)
    user_id = await session_user_id(
        engine, token=token, csrf_token=csrf, auth_secret=auth_secret(settings)
    )
    if user_id is None:
        raise HTTPException(status_code=401, detail="invalid_session_or_csrf")
    return user_id


async def mutation_user(request: Request, token: str | None, csrf: str | None) -> UUID:
    if csrf is None:
        raise HTTPException(status_code=401, detail="csrf_required")
    return await current_user(request, token, csrf)


def own_response(profile: ProfileView) -> OwnProfileResponse:
    return OwnProfileResponse(
        public_id=profile.public_id,
        display_name=profile.display_name,
        bio=profile.bio,
        selected_city_id=str(profile.selected_city_id)
        if profile.selected_city_id
        else None,
        city_name=profile.city_name,
        avatar_url=f"/api/profiles/{profile.public_id}/avatar?v={profile.version}"
        if profile.avatar_asset_id
        else None,
        version=profile.version,
        next_name_change_at=profile.next_name_change_at.isoformat()
        if profile.next_name_change_at
        else None,
        organizer_status=profile.organizer_status,
        successful_events=profile.successful_events,
        upcoming_count=profile.upcoming_count,
        completed_count=profile.completed_count,
    )


@router.get(
    "/public/profiles/{public_id}", response_model=AnonymousPublicProfileResponse
)
async def anonymous_public_profile(
    public_id: str, request: Request
) -> AnonymousPublicProfileResponse:
    if not (len(public_id) == 8 and public_id.isdigit()):
        raise HTTPException(status_code=404, detail="profile_not_found")
    _, _, engine = dependencies(request)
    try:
        profile = await load_profile(engine, public_id=public_id)
    except ProfileNotFound as error:
        raise HTTPException(status_code=404, detail="profile_not_found") from error
    items = await profile_events(
        engine, user_id=profile.user_id, state="upcoming", limit=20, offset=0
    )
    return AnonymousPublicProfileResponse(
        public_id=profile.public_id,
        display_name=profile.display_name,
        bio=profile.bio,
        avatar_url=(
            f"/api/public/profiles/{profile.public_id}/avatar?v={profile.version}"
            if profile.avatar_asset_id
            else None
        ),
        organizer_status=profile.organizer_status,
        successful_events=profile.successful_events,
        upcoming_events=[EventResponse.model_validate(item) for item in items],
    )


@router.get("/public/profiles/{public_id}/avatar")
async def anonymous_profile_avatar(public_id: str, request: Request) -> Response:
    settings, _, engine = dependencies(request)
    async with engine.connect() as connection:
        key = await connection.scalar(
            text(
                """
                SELECT a.storage_key FROM accounts.profiles p
                JOIN accounts.users u ON u.id=p.user_id AND u.status='active'
                JOIN media.assets a ON a.id=p.avatar_asset_id AND a.state='ready'
                WHERE p.public_id=:id
                """
            ),
            {"id": public_id},
        )
    if key is None:
        raise HTTPException(status_code=404, detail="avatar_not_found")
    path = settings.media_root / key
    if not path.is_file():
        raise HTTPException(status_code=404, detail="avatar_not_found")
    return FileResponse(
        path, media_type="image/webp", headers={"Cache-Control": "public, max-age=300"}
    )


@router.get("/account/profile", response_model=OwnProfileResponse)
async def get_own_profile(
    request: Request, token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None
) -> OwnProfileResponse:
    _, _, engine = dependencies(request)
    return own_response(
        await load_profile(engine, user_id=await current_user(request, token))
    )


@router.patch("/account/profile", response_model=OwnProfileResponse)
async def patch_profile(
    body: UpdateProfileRequest,
    request: Request,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    csrf: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
) -> OwnProfileResponse:
    settings, _, engine = dependencies(request)
    validate_origin(request, settings)
    try:
        profile = await update_profile(
            engine,
            user_id=await mutation_user(request, token, csrf),
            display_name=body.display_name,
            bio=body.bio,
            selected_city_id=body.selected_city_id,
            expected_version=body.version,
        )
    except ProfileConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ProfileError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return own_response(profile)


@router.patch("/account/profile/city", response_model=OwnProfileResponse)
async def patch_profile_city(
    body: UpdateProfileCityRequest,
    request: Request,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    csrf: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
) -> OwnProfileResponse:
    settings, _, engine = dependencies(request)
    validate_origin(request, settings)
    try:
        profile = await update_profile_city(
            engine,
            user_id=await mutation_user(request, token, csrf),
            selected_city_id=body.selected_city_id,
            expected_version=body.version,
        )
    except ProfileConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ProfileError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return own_response(profile)


@router.get("/profiles/{public_id}", response_model=PublicProfileResponse)
async def public_profile(
    public_id: str,
    request: Request,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> PublicProfileResponse:
    if not (len(public_id) == 8 and public_id.isdigit()):
        raise HTTPException(status_code=404, detail="profile_not_found")
    _, redis, engine = dependencies(request)
    viewer = await current_user(request, token)
    count = await redis.incr(f"profile-lookup:{viewer}")  # pyright: ignore[reportUnknownMemberType]
    if count == 1:
        await redis.expire(f"profile-lookup:{viewer}", 60)
    if count > 30:
        raise HTTPException(status_code=429, detail="profile_lookup_limited")
    try:
        profile = await load_profile(engine, public_id=public_id)
    except ProfileNotFound as error:
        raise HTTPException(status_code=404, detail="profile_not_found") from error
    return PublicProfileResponse(
        public_id=profile.public_id,
        display_name=profile.display_name,
        bio=profile.bio,
        avatar_url=f"/api/profiles/{profile.public_id}/avatar?v={profile.version}"
        if profile.avatar_asset_id
        else None,
        organizer_status=profile.organizer_status,
        successful_events=profile.successful_events,
    )


@router.get("/profiles/{public_id}/events", response_model=EventsResponse)
async def get_profile_events(
    public_id: str,
    request: Request,
    state: Literal["upcoming", "completed"],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=20)] = 10,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> EventsResponse:
    await current_user(request, token)
    _, _, engine = dependencies(request)
    try:
        profile = await load_profile(engine, public_id=public_id)
    except ProfileNotFound as error:
        raise HTTPException(status_code=404, detail="profile_not_found") from error
    items = await profile_events(
        engine, user_id=profile.user_id, state=state, limit=limit + 1, offset=offset
    )
    has_more = len(items) > limit
    return EventsResponse(
        items=[EventResponse.model_validate(item) for item in items[:limit]],
        next_offset=offset + limit if has_more else None,
    )


@router.get("/account/events", response_model=EventsResponse)
async def get_account_events(
    request: Request,
    state: Literal["upcoming", "completed"],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=20)] = 10,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> EventsResponse:
    _, _, engine = dependencies(request)
    user_id = await current_user(request, token)
    items = await account_events(
        engine, user_id=user_id, state=state, limit=limit + 1, offset=offset
    )
    has_more = len(items) > limit
    return EventsResponse(
        items=[EventResponse.model_validate(item) for item in items[:limit]],
        next_offset=offset + limit if has_more else None,
    )


@router.get("/account/notifications", response_model=list[NotificationResponse])
async def get_account_notifications(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=50)] = 30,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> list[NotificationResponse]:
    _, _, engine = dependencies(request)
    user_id = await current_user(request, token)
    async with engine.connect() as connection:
        rows = (
            (
                await connection.execute(
                    text(
                        """
                    SELECT id,kind,importance,title,body,deep_link,created_at,read_at
                    FROM communication.notifications
                    WHERE recipient_user_id=:user
                      AND (expires_at IS NULL OR expires_at>now())
                    ORDER BY created_at DESC,id DESC LIMIT :limit
                    """
                    ),
                    {"user": user_id, "limit": limit},
                )
            )
            .mappings()
            .all()
        )
    return [NotificationResponse.model_validate(row) for row in rows]


@router.post("/profiles/{public_id}/reports", status_code=201)
async def report_profile(
    public_id: str,
    body: ReportRequest,
    request: Request,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    csrf: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
) -> dict[str, str]:
    settings, _, engine = dependencies(request)
    validate_origin(request, settings)
    reporter = await mutation_user(request, token, csrf)
    try:
        await create_report(
            engine,
            reporter_id=reporter,
            subject=await load_profile(engine, public_id=public_id),
            reason=body.reason,
            comment=body.comment,
        )
    except ProfileNotFound as error:
        raise HTTPException(status_code=404, detail="profile_not_found") from error
    except ProfileConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ProfileError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {"status": "accepted"}


@router.put("/account/avatar", response_model=OwnProfileResponse)
async def put_avatar(
    request: Request,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    csrf: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
) -> OwnProfileResponse:
    settings, _, engine = dependencies(request)
    validate_origin(request, settings)
    user_id = await mutation_user(request, token, csrf)
    if request.headers.get("content-type", "").split(";", 1)[0] not in {
        "image/jpeg",
        "image/png",
        "image/webp",
    }:
        raise HTTPException(status_code=415, detail="unsupported_image")
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > 12 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="image_too_large")
    asset_id = uuid4()
    source = settings.media_root / "quarantine" / f"{asset_id}.upload"
    destination = settings.media_root / "avatars" / f"{asset_id}.webp"
    await to_thread.run_sync(source.parent.mkdir, 0o750, True, True)
    await to_thread.run_sync(source.write_bytes, bytes(data))
    try:
        await to_thread.run_sync(AvatarImageProcessor().process, source, destination)
    except UnsafeImageError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    checksum = await to_thread.run_sync(
        lambda: hashlib.sha256(destination.read_bytes()).hexdigest()
    )
    old_path: Path | None = None
    async with engine.begin() as connection:
        old = (
            (
                await connection.execute(
                    text(
                        """SELECT a.id, a.storage_key FROM accounts.profiles p LEFT JOIN media.assets a ON a.id=p.avatar_asset_id WHERE p.user_id=:user FOR UPDATE OF p"""
                    ),
                    {"user": user_id},
                )
            )
            .mappings()
            .one()
        )
        await connection.execute(
            text("""INSERT INTO media.assets (id,owner_user_id,purpose,state,storage_key,mime_type,byte_size,width,height,checksum_sha256)
            VALUES (:id,:user,'profile_avatar','ready',:key,'image/webp',:size,256,256,:checksum)"""),
            {
                "id": asset_id,
                "user": user_id,
                "key": f"avatars/{asset_id}.webp",
                "size": destination.stat().st_size,
                "checksum": checksum,
            },
        )
        await connection.execute(
            text(
                "UPDATE accounts.profiles SET avatar_asset_id=:asset,version=version+1,updated_at=now() WHERE user_id=:user"
            ),
            {"asset": asset_id, "user": user_id},
        )
        if old["id"]:
            retained = await connection.scalar(
                text(
                    "SELECT 1 FROM trust_safety.profile_reports WHERE avatar_asset_id=:id AND status IN ('pending','reviewed')"
                ),
                {"id": old["id"]},
            )
            if retained is None:
                await connection.execute(
                    text(
                        "UPDATE media.assets SET state='deleted',updated_at=now() WHERE id=:id"
                    ),
                    {"id": old["id"]},
                )
                old_path = settings.media_root / old["storage_key"]
    if old_path:
        await to_thread.run_sync(old_path.unlink, True)
    return own_response(await load_profile(engine, user_id=user_id))


@router.delete("/account/avatar", response_model=OwnProfileResponse)
async def delete_avatar(
    request: Request,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    csrf: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
) -> OwnProfileResponse:
    settings, _, engine = dependencies(request)
    validate_origin(request, settings)
    user_id = await mutation_user(request, token, csrf)
    old_path: Path | None = None
    async with engine.begin() as connection:
        old = (
            (
                await connection.execute(
                    text(
                        """SELECT a.id,a.storage_key FROM accounts.profiles p LEFT JOIN media.assets a ON a.id=p.avatar_asset_id WHERE p.user_id=:user FOR UPDATE OF p"""
                    ),
                    {"user": user_id},
                )
            )
            .mappings()
            .one()
        )
        await connection.execute(
            text(
                "UPDATE accounts.profiles SET avatar_asset_id=NULL,version=version+1,updated_at=now() WHERE user_id=:user"
            ),
            {"user": user_id},
        )
        if old["id"]:
            retained = await connection.scalar(
                text(
                    "SELECT 1 FROM trust_safety.profile_reports WHERE avatar_asset_id=:id AND status IN ('pending','reviewed')"
                ),
                {"id": old["id"]},
            )
            if retained is None:
                await connection.execute(
                    text(
                        "UPDATE media.assets SET state='deleted',updated_at=now() WHERE id=:id"
                    ),
                    {"id": old["id"]},
                )
                old_path = settings.media_root / old["storage_key"]
    if old_path:
        await to_thread.run_sync(old_path.unlink, True)
    return own_response(await load_profile(engine, user_id=user_id))


@router.get("/profiles/{public_id}/avatar")
async def avatar(
    public_id: str,
    request: Request,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> Response:
    await current_user(request, token)
    settings, _, engine = dependencies(request)
    async with engine.connect() as connection:
        key = await connection.scalar(
            text(
                """SELECT a.storage_key FROM accounts.profiles p JOIN accounts.users u ON u.id=p.user_id AND u.status='active' JOIN media.assets a ON a.id=p.avatar_asset_id AND a.state='ready' WHERE p.public_id=:id"""
            ),
            {"id": public_id},
        )
    if key is None:
        raise HTTPException(status_code=404, detail="avatar_not_found")
    path = settings.media_root / key
    if not path.is_file():
        raise HTTPException(status_code=404, detail="avatar_not_found")
    return FileResponse(
        path, media_type="image/webp", headers={"Cache-Control": "private, max-age=300"}
    )
