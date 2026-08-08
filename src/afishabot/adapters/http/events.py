import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Cookie, Header, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import text

from afishabot.adapters.http.auth import CSRF_HEADER, SESSION_COOKIE
from afishabot.adapters.http.profiles import (
    auth_secret,
    current_user,
    dependencies,
    mutation_user,
    validate_origin,
)
from afishabot.modules.accounts.application.profiles import session_user_id
from afishabot.modules.discovery.infrastructure.nominatim import (
    NominatimReverseGeocoder,
)
from afishabot.modules.discovery.application.street_anchors import (
    StreetAnchorError,
    save_street_anchor,
)
from afishabot.modules.discovery.public.geo import (
    ReverseGeocodingMalformed,
    ReverseGeocodingNotFound,
    ReverseGeocodingUnavailable,
)
from afishabot.modules.events.application.create_event import (
    CreateEventCommand,
    EventCreationConflict,
    EventCreationError,
    create_event,
    find_created_event,
)
from afishabot.modules.events.application.manage_event import (
    CancelReason,
    ChangeEventCommand,
    EventManagementConflict,
    EventManagementError,
    EventManagementNotFound,
    cancel_event,
    management_view,
    submit_change,
)
from afishabot.modules.events.application.public_discovery import (
    PublicEventNotFound,
    event_detail,
    event_feed,
    event_photo_key,
)
from afishabot.modules.events.application.participation import (
    ExclusionReason,
    ParticipationError,
    ParticipationNotFound,
    exclude_participant,
    join_event,
    leave_event,
    organizer_roster,
    set_interest,
)

router = APIRouter(prefix="/events", tags=["events"])


class CreateEventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=60)
    description: str = Field(min_length=1, max_length=1000)
    category_id: UUID
    city_id: UUID
    starts_at: datetime
    ends_at: datetime
    capacity: int | None = Field(default=None, ge=3, le=2_147_483_647)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    address_visibility: Literal[
        "street_only", "exact_participants", "exact_public"
    ]
    location_note: str | None = Field(default=None, max_length=80)
    exact_address_confirmed: bool
    photo_upload_id: UUID

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("text must not be blank")
        return normalized

    @field_validator("description")
    @classmethod
    def description_must_not_be_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("text must not be blank")
        return normalized

    @field_validator("location_note")
    @classmethod
    def location_note_must_be_compact(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        return normalized or None

    @field_validator("starts_at", "ends_at")
    @classmethod
    def date_must_include_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timezone is required")
        return value.astimezone(UTC)


class CreateEventResponse(BaseModel):
    event_id: UUID
    status: Literal["published", "pending_review"]


class ChangeEventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=60)
    description: str = Field(min_length=1, max_length=1000)
    starts_at: datetime
    ends_at: datetime
    photo_upload_id: UUID | None = None

    @field_validator("title", "description")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        normalized = " ".join(value.split()) if len(value) <= 60 else value.strip()
        if not normalized:
            raise ValueError("text must not be blank")
        return normalized

    @field_validator("starts_at", "ends_at")
    @classmethod
    def change_date_must_include_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timezone is required")
        return value.astimezone(UTC)


class CancelEventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: CancelReason


class ExcludeParticipantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: ExclusionReason
    note: str | None = Field(default=None, max_length=300)


async def optional_viewer(request: Request, token: str | None) -> UUID | None:
    if token is None:
        return None
    settings, _, engine = dependencies(request)
    return await session_user_id(
        engine, token=token, csrf_token=None, auth_secret=auth_secret(settings)
    )


@router.get("")
async def published_events(
    request: Request,
    city_id: Annotated[UUID, Query()],
    view: Annotated[Literal["list", "map"], Query()] = "list",
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> dict[str, object]:
    _, _, engine = dependencies(request)
    return {
        "items": await event_feed(
            engine,
            city_id=city_id,
            viewer_id=await optional_viewer(request, token),
            view=view,
        )
    }


@router.post("", response_model=CreateEventResponse, status_code=201)
async def submit_event(
    body: CreateEventRequest,
    request: Request,
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    csrf: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
) -> CreateEventResponse:
    settings, _, engine = dependencies(request)
    validate_origin(request, settings)
    user_id = await mutation_user(request, token, csrf)
    if body.address_visibility == "exact_public" and not body.exact_address_confirmed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="exact_address_confirmation_required",
        )
    serialized = json.dumps(
        body.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    fingerprint = hashlib.sha256(serialized.encode()).hexdigest()
    try:
        previous = await find_created_event(
            engine,
            user_id=user_id,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
        )
    except EventCreationConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    if previous is not None:
        return CreateEventResponse(
            event_id=previous.event_id,
            status=previous.publication_status,
        )

    geocoder = cast(NominatimReverseGeocoder, request.app.state.reverse_geocoder)
    try:
        canonical_address = await geocoder.reverse(
            latitude=body.latitude,
            longitude=body.longitude,
            locale="ru",
        )
    except ReverseGeocodingNotFound as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="address_not_found",
        ) from error
    except (ReverseGeocodingUnavailable, ReverseGeocodingMalformed) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="address_unavailable",
        ) from error

    street_anchor_id: UUID | None = None
    if body.address_visibility != "exact_public":
        if canonical_address.street is None:
            raise HTTPException(status_code=422, detail="street_required")
        try:
            candidate = await geocoder.street_anchor(
                street=canonical_address.street,
                city=canonical_address.city,
                locale="ru",
            )
            street_anchor_id = await save_street_anchor(
                engine,
                city_id=body.city_id,
                street=canonical_address.street,
                candidate=candidate,
            )
        except (ReverseGeocodingNotFound, StreetAnchorError) as error:
            raise HTTPException(
                status_code=422, detail="street_anchor_unavailable"
            ) from error
        except (ReverseGeocodingUnavailable, ReverseGeocodingMalformed) as error:
            raise HTTPException(
                status_code=503, detail="street_anchor_unavailable"
            ) from error
    try:
        created = await create_event(
            engine,
            CreateEventCommand(
                user_id=user_id,
                idempotency_key=idempotency_key,
                request_fingerprint=fingerprint,
                title=body.title,
                description=body.description,
                category_id=body.category_id,
                city_id=body.city_id,
                starts_at=body.starts_at,
                ends_at=body.ends_at,
                capacity=body.capacity,
                latitude=body.latitude,
                longitude=body.longitude,
                address_visibility=body.address_visibility,
                location_note=body.location_note,
                photo_upload_id=body.photo_upload_id,
                canonical_address=canonical_address,
                street_anchor_id=street_anchor_id,
            ),
        )
    except EventCreationConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except EventCreationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return CreateEventResponse(
        event_id=created.event_id,
        status=created.publication_status,
    )


@router.get("/{event_id}")
async def published_event_detail(
    event_id: UUID,
    request: Request,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> dict[str, object]:
    _, _, engine = dependencies(request)
    try:
        return await event_detail(
            engine,
            event_id=event_id,
            viewer_id=await optional_viewer(request, token),
        )
    except PublicEventNotFound as error:
        raise HTTPException(status_code=404, detail="event_not_found") from error


@router.get("/{event_id}/photo")
async def published_event_photo(event_id: UUID, request: Request) -> Response:
    settings, _, engine = dependencies(request)
    try:
        storage_key = await event_photo_key(engine, event_id)
    except PublicEventNotFound as error:
        raise HTTPException(status_code=404, detail="photo_not_found") from error
    path = Path(settings.media_root) / storage_key
    if not path.is_file():
        raise HTTPException(status_code=404, detail="photo_not_found")
    return FileResponse(
        path, media_type="image/webp", headers={"Cache-Control": "public, max-age=300"}
    )


@router.put("/{event_id}/interest")
async def mark_event_interesting(
    event_id: UUID,
    request: Request,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    csrf: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
) -> dict[str, object]:
    settings, _, engine = dependencies(request)
    validate_origin(request, settings)
    try:
        return await set_interest(
            engine,
            event_id=event_id,
            user_id=await mutation_user(request, token, csrf),
            active=True,
        )
    except ParticipationNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.delete("/{event_id}/interest")
async def unmark_event_interesting(
    event_id: UUID,
    request: Request,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    csrf: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
) -> dict[str, object]:
    settings, _, engine = dependencies(request)
    validate_origin(request, settings)
    try:
        return await set_interest(
            engine,
            event_id=event_id,
            user_id=await mutation_user(request, token, csrf),
            active=False,
        )
    except ParticipationNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/{event_id}/join")
async def join_published_event(
    event_id: UUID,
    request: Request,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    csrf: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
) -> dict[str, object]:
    settings, _, engine = dependencies(request)
    validate_origin(request, settings)
    try:
        return await join_event(
            engine,
            event_id=event_id,
            user_id=await mutation_user(request, token, csrf),
        )
    except ParticipationNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ParticipationError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/{event_id}/leave")
async def leave_published_event(
    event_id: UUID,
    request: Request,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    csrf: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
) -> dict[str, object]:
    settings, _, engine = dependencies(request)
    validate_origin(request, settings)
    try:
        return await leave_event(
            engine,
            event_id=event_id,
            user_id=await mutation_user(request, token, csrf),
        )
    except ParticipationNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ParticipationError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/{event_id}/manage")
async def get_event_management(
    event_id: UUID,
    request: Request,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> dict[str, object]:
    _, _, engine = dependencies(request)
    try:
        return await management_view(
            engine, event_id=event_id, user_id=await current_user(request, token)
        )
    except EventManagementNotFound as error:
        raise HTTPException(status_code=404, detail="event_not_found") from error


@router.get("/{event_id}/manage/roster")
async def get_event_roster(
    event_id: UUID,
    request: Request,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> dict[str, object]:
    _, _, engine = dependencies(request)
    try:
        return await organizer_roster(
            engine,
            event_id=event_id,
            organizer_id=await current_user(request, token),
        )
    except ParticipationNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/{event_id}/participants/{participation_id}/exclude", status_code=204)
async def exclude_event_participant(
    event_id: UUID,
    participation_id: UUID,
    body: ExcludeParticipantRequest,
    request: Request,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    csrf: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
) -> None:
    settings, _, engine = dependencies(request)
    validate_origin(request, settings)
    try:
        await exclude_participant(
            engine,
            event_id=event_id,
            organizer_id=await mutation_user(request, token, csrf),
            participation_id=participation_id,
            reason=body.reason,
            note=body.note,
        )
    except ParticipationNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ParticipationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/{event_id}/manage/photo")
async def get_managed_event_photo(
    event_id: UUID,
    request: Request,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> Response:
    settings, _, engine = dependencies(request)
    user_id = await current_user(request, token)
    try:
        view = await management_view(engine, event_id=event_id, user_id=user_id)
    except EventManagementNotFound as error:
        raise HTTPException(status_code=404, detail="event_not_found") from error
    async with engine.connect() as connection:
        storage_key = await connection.scalar(
            text("SELECT storage_key FROM media.assets WHERE id=:id AND state='ready'"),
            {"id": view["media_asset_id"]},
        )
    if storage_key is None:
        raise HTTPException(status_code=404, detail="photo_not_found")
    path = Path(settings.media_root) / storage_key
    if not path.is_file():
        raise HTTPException(status_code=404, detail="photo_not_found")
    return FileResponse(path, media_type="image/webp", headers={"Cache-Control": "private, no-store"})


@router.post("/{event_id}/revisions", status_code=202)
async def revise_published_event(
    event_id: UUID,
    body: ChangeEventRequest,
    request: Request,
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    csrf: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
) -> dict[str, object]:
    settings, _, engine = dependencies(request)
    validate_origin(request, settings)
    user_id = await mutation_user(request, token, csrf)
    serialized = json.dumps(body.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    try:
        revision_id = await submit_change(
            engine,
            ChangeEventCommand(
                event_id=event_id,
                user_id=user_id,
                idempotency_key=idempotency_key,
                request_fingerprint=hashlib.sha256(serialized.encode()).hexdigest(),
                title=body.title,
                description=body.description,
                starts_at=body.starts_at,
                ends_at=body.ends_at,
                photo_upload_id=body.photo_upload_id,
            ),
        )
    except EventManagementNotFound as error:
        raise HTTPException(status_code=404, detail="event_not_found") from error
    except EventManagementConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except EventManagementError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {"revision_id": revision_id, "status": "pending_review"}


@router.post("/{event_id}/cancel", status_code=204)
async def cancel_published_event(
    event_id: UUID,
    body: CancelEventRequest,
    request: Request,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    csrf: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
) -> None:
    settings, _, engine = dependencies(request)
    validate_origin(request, settings)
    try:
        await cancel_event(
            engine,
            event_id=event_id,
            user_id=await mutation_user(request, token, csrf),
            reason=body.reason,
        )
    except EventManagementConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except EventManagementError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
