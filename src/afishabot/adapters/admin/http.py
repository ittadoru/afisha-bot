import asyncio
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Cookie, Header, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from afishabot.adapters.tasks.celery_app import estimate_storage_savings_task
from afishabot.core.config import Settings
from afishabot.modules.events.application.manage_event import (
    CancelReason,
    EventManagementConflict,
    EventManagementError,
    cancel_special_event,
    create_special_event,
)
from afishabot.modules.media.application.storage_analysis import (
    inventory,
    queue_estimate,
    save_inventory,
)
from afishabot.modules.media.application.storage_analysis import (
    latest as latest_storage_analysis,
)
from afishabot.modules.trust_safety.application.event_moderation import (
    ModerationConflict,
    ModerationNotFound,
    ReviewDecision,
    decide_review,
    review_detail,
    review_queue,
)
from afishabot.modules.trust_safety.application.staff_admin import (
    AdminAuthBlocked,
    AdminAuthDenied,
    AdminAuthUnavailable,
    StaffIdentity,
    audit_page,
    authenticate_staff,
    consume_login_bootstrap,
    contextual_hash,
    create_login_bootstrap,
    dashboard_counts,
    load_staff_mutation_session,
    load_staff_read_session,
    load_staff_session,
    record_admin_event,
    revoke_staff_session,
)

router = APIRouter(prefix="/admin", tags=["admin"])

SESSION_COOKIE = "__Host-afisha_admin"
BOOTSTRAP_COOKIE = "__Host-afisha_admin_login"
CSRF_HEADER = "X-Afisha-Admin-CSRF"


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    login: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class BootstrapResponse(BaseModel):
    csrf_token: str


class StaffResponse(BaseModel):
    login: str
    role: str


class LoginResponse(BaseModel):
    account: StaffResponse
    csrf_token: str


class DashboardResponse(BaseModel):
    active_users: int
    upcoming_events: int
    pending_events: int
    open_profile_reports: int
    active_moderators: int


class SystemMetricsResponse(BaseModel):
    collected_at: datetime
    disk: dict[str, int]
    memory: dict[str, int]
    cpu: dict[str, float]
    uptime_seconds: int
    containers: list[dict[str, str | float]]


class ImageAnalysisResponse(BaseModel):
    collected_at: datetime
    source: Literal["database"]
    file_count: int
    total_bytes: int
    permanent_file_count: int
    permanent_bytes: int
    temporary_file_count: int
    temporary_bytes: int
    formats: list[dict[str, str | int]]
    purposes: list[dict[str, str | int]]
    directories: list[dict[str, str | int | float]]
    estimate_status: Literal["idle", "queued", "running", "completed", "failed"] = (
        "idle"
    )
    estimate_job_id: str | None = None
    estimate_collected_at: datetime | None = None
    estimate: dict[str, int | float] | None = None


class ImageEstimateQueuedResponse(BaseModel):
    job_id: UUID
    status: Literal["queued"] = "queued"


class AuditEntryResponse(BaseModel):
    id: str
    created_at: datetime
    actor: str | None
    action: str
    result: str


class AuditPageResponse(BaseModel):
    items: list[AuditEntryResponse]
    next_before: datetime | None


class ReviewDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision_id: UUID
    reason: (
        Literal[
            "unclear_description",
            "prohibited_content",
            "paid_or_advertising",
            "inappropriate_photo",
            "invalid_place_or_time",
            "duplicate_or_spam",
        ]
        | None
    ) = None


class CancelSpecialRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: CancelReason


class CreateSpecialRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=60)
    description: str = Field(min_length=1, max_length=1000)
    city_id: UUID
    starts_at: datetime
    ends_at: datetime
    place: str = Field(default="", max_length=500)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class CreatedSpecialResponse(BaseModel):
    id: str


@router.post("/auth/bootstrap", response_model=BootstrapResponse)
async def bootstrap(request: Request, response: Response) -> BootstrapResponse:
    settings, redis, engine = _dependencies(request)
    origin = _validate_admin_request(request, settings, require_origin=True)
    secret = _required_secret(settings)
    source_digest = contextual_hash(secret, "admin-source", _request_source(request))
    try:
        cookie, csrf_token = await create_login_bootstrap(
            redis,
            origin=origin,
            auth_secret=secret,
        )
    except AdminAuthUnavailable as error:
        raise _error(503, "admin_auth_unavailable") from error
    await record_admin_event(
        engine,
        action="staff.login_bootstrap",
        result="success",
        source_digest=source_digest,
    )
    response.set_cookie(
        BOOTSTRAP_COOKIE,
        cookie,
        max_age=300,
        secure=True,
        httponly=True,
        samesite="strict",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return BootstrapResponse(csrf_token=csrf_token)


@router.post("/auth/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    bootstrap_cookie: Annotated[str | None, Cookie(alias=BOOTSTRAP_COOKIE)] = None,
    csrf_token: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
) -> LoginResponse:
    settings, redis, engine = _dependencies(request)
    origin = _validate_admin_request(request, settings, require_origin=True)
    secret = _required_secret(settings)
    if bootstrap_cookie is None or csrf_token is None:
        raise _login_error()
    try:
        await consume_login_bootstrap(
            redis,
            cookie=bootstrap_cookie,
            csrf_token=csrf_token,
            origin=origin,
            auth_secret=secret,
        )
        session = await authenticate_staff(
            engine,
            login=body.login,
            password=body.password,
            source=_request_source(request),
            auth_secret=secret,
        )
    except AdminAuthBlocked as error:
        raise _error(429, "admin_login_blocked") from error
    except AdminAuthDenied as error:
        raise _login_error() from error
    except AdminAuthUnavailable as error:
        raise _error(503, "admin_auth_unavailable") from error
    response.delete_cookie(BOOTSTRAP_COOKIE, path="/")
    response.set_cookie(
        SESSION_COOKIE,
        session.token,
        max_age=8 * 60 * 60,
        secure=True,
        httponly=True,
        samesite="strict",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return LoginResponse(
        account=_staff_response(session.identity),
        csrf_token=session.csrf_token,
    )


@router.get("/account/me", response_model=StaffResponse)
async def me(
    request: Request,
    response: Response,
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> StaffResponse:
    settings, _, engine = _dependencies(request)
    _validate_admin_request(request, settings)
    identity, csrf_token = await _require_session(
        engine, session_token, _required_secret(settings), rotate_csrf=True
    )
    response.headers[CSRF_HEADER] = csrf_token
    response.headers["Cache-Control"] = "no-store"
    return _staff_response(identity)


@router.post("/auth/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    csrf_token: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
) -> None:
    settings, _, engine = _dependencies(request)
    _validate_admin_request(request, settings, require_origin=True)
    if session_token is None or csrf_token is None:
        raise _error(401, "admin_session_required")
    revoked = await revoke_staff_session(
        engine,
        token=session_token,
        csrf_token=csrf_token,
        auth_secret=_required_secret(settings),
    )
    if not revoked:
        raise _error(401, "admin_session_required")
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard(
    request: Request,
    response: Response,
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> DashboardResponse:
    settings, _, engine = _dependencies(request)
    _validate_admin_request(request, settings)
    _, _ = await _require_session(engine, session_token, _required_secret(settings))
    response.headers["Cache-Control"] = "no-store"
    return DashboardResponse(**asdict(await dashboard_counts(engine)))


@router.get("/system/metrics", response_model=SystemMetricsResponse)
async def system_metrics(
    request: Request,
    response: Response,
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> SystemMetricsResponse:
    settings, _, engine = _dependencies(request)
    _validate_admin_request(request, settings)
    _, _ = await _require_session(engine, session_token, _required_secret(settings))
    try:
        raw = json.loads(settings.admin_metrics_file.read_text(encoding="utf-8"))
        result = SystemMetricsResponse.model_validate(raw)
    except (OSError, ValueError) as error:
        raise _error(503, "system_metrics_unavailable") from error
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post("/system/metrics/refresh", response_model=SystemMetricsResponse)
async def refresh_system_metrics(
    request: Request,
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    csrf_token: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
) -> SystemMetricsResponse:
    settings, _, engine = _dependencies(request)
    _validate_admin_request(request, settings, require_origin=True)
    if session_token is None or csrf_token is None:
        raise _error(401, "admin_session_required")
    identity = await load_staff_mutation_session(
        engine,
        token=session_token,
        csrf_token=csrf_token,
        auth_secret=_required_secret(settings),
    )
    if identity is None:
        raise _error(401, "admin_session_required")
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_unix_connection(str(settings.admin_metrics_socket)), timeout=2
        )
        try:
            payload = await asyncio.wait_for(reader.read(), timeout=15)
        finally:
            writer.close()
            await writer.wait_closed()
        return SystemMetricsResponse.model_validate_json(payload)
    except (OSError, TimeoutError, ValueError) as error:
        raise _error(503, "system_metrics_refresh_unavailable") from error


@router.get("/media/analysis", response_model=ImageAnalysisResponse)
async def image_analysis(
    request: Request,
    response: Response,
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> ImageAnalysisResponse:
    settings, _, engine = _dependencies(request)
    _validate_admin_request(request, settings)
    _, _ = await _require_session(engine, session_token, _required_secret(settings))
    result = await latest_storage_analysis(engine)
    if result is None:
        raise _error(404, "storage_analysis_not_collected")
    response.headers["Cache-Control"] = "no-store"
    return ImageAnalysisResponse.model_validate(result)


@router.post("/media/analysis/refresh", response_model=ImageAnalysisResponse)
async def refresh_image_analysis(
    request: Request,
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    csrf_token: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
) -> ImageAnalysisResponse:
    settings, _, engine = _dependencies(request)
    _validate_admin_request(request, settings, require_origin=True)
    if session_token is None or csrf_token is None:
        raise _error(401, "admin_session_required")
    if (
        await load_staff_mutation_session(
            engine,
            token=session_token,
            csrf_token=csrf_token,
            auth_secret=_required_secret(settings),
        )
        is None
    ):
        raise _error(401, "admin_session_required")
    result = await inventory(engine)
    await save_inventory(engine, result)
    latest = await latest_storage_analysis(engine)
    return ImageAnalysisResponse.model_validate(latest or result)


@router.post(
    "/media/analysis/estimate",
    response_model=ImageEstimateQueuedResponse,
    status_code=202,
)
async def estimate_image_savings(
    request: Request,
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    csrf_token: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
) -> ImageEstimateQueuedResponse:
    settings, _, engine = _dependencies(request)
    _validate_admin_request(request, settings, require_origin=True)
    if session_token is None or csrf_token is None:
        raise _error(401, "admin_session_required")
    if (
        await load_staff_mutation_session(
            engine,
            token=session_token,
            csrf_token=csrf_token,
            auth_secret=_required_secret(settings),
        )
        is None
    ):
        raise _error(401, "admin_session_required")
    try:
        job_id = await queue_estimate(engine)
    except RuntimeError as error:
        raise _error(409, "storage_estimate_running") from error
    estimate_storage_savings_task.delay(str(job_id))
    return ImageEstimateQueuedResponse(job_id=job_id)


@router.get("/audit", response_model=AuditPageResponse)
async def audit(
    request: Request,
    response: Response,
    before: Annotated[datetime | None, Query()] = None,
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> AuditPageResponse:
    settings, _, engine = _dependencies(request)
    _validate_admin_request(request, settings)
    _, _ = await _require_session(engine, session_token, _required_secret(settings))
    rows = await audit_page(engine, before=before)
    items = [
        AuditEntryResponse(
            id=str(row["id"]),
            created_at=cast(datetime, row["created_at"]),
            actor=cast(str | None, row["actor"]),
            action=cast(str, row["action"]),
            result=cast(str, row["result"]),
        )
        for row in rows
    ]
    response.headers["Cache-Control"] = "no-store"
    return AuditPageResponse(
        items=items,
        next_before=items[-1].created_at if len(items) == 50 else None,
    )


@router.get("/events/reviews")
async def event_reviews(
    request: Request,
    response: Response,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=50)] = 25,
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> dict[str, object]:
    settings, _, engine = _dependencies(request)
    _validate_admin_request(request, settings)
    _, _ = await _require_session(engine, session_token, _required_secret(settings))
    rows = await review_queue(engine, offset=offset, limit=limit + 1)
    return {
        "items": rows[:limit],
        "next_offset": offset + limit if len(rows) > limit else None,
    }


@router.get("/events/reviews/{review_id}")
async def event_review_detail(
    review_id: UUID,
    request: Request,
    response: Response,
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> dict[str, object]:
    settings, _, engine = _dependencies(request)
    _validate_admin_request(request, settings)
    _, _ = await _require_session(engine, session_token, _required_secret(settings))
    try:
        detail = await review_detail(engine, review_id)
    except ModerationNotFound as error:
        raise _error(404, "review_not_found") from error
    detail["photo_url"] = f"/api/admin/events/reviews/{review_id}/photo"
    return detail


@router.get("/events/reviews/{review_id}/photo")
async def event_review_photo(
    review_id: UUID,
    request: Request,
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> Response:
    settings, _, engine = _dependencies(request)
    _validate_admin_request(request, settings)
    await _require_session(engine, session_token, _required_secret(settings))
    try:
        detail = await review_detail(engine, review_id)
    except ModerationNotFound as error:
        raise _error(404, "review_not_found") from error
    path = (
        Path(settings.media_root) / "event-staging" / f"{detail['media_asset_id']}.webp"
    )
    if not path.is_file():
        raise _error(404, "photo_not_found")
    return FileResponse(
        path, media_type="image/webp", headers={"Cache-Control": "private, no-store"}
    )


@router.post("/events/reviews/{review_id}/{action}", status_code=204)
async def decide_event_review(
    review_id: UUID,
    action: Literal["approve", "reject"],
    body: ReviewDecisionRequest,
    request: Request,
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    csrf_token: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
) -> None:
    settings, _, engine = _dependencies(request)
    _validate_admin_request(request, settings, require_origin=True)
    if session_token is None or csrf_token is None:
        raise _error(401, "admin_session_required")
    identity = await load_staff_mutation_session(
        engine,
        token=session_token,
        csrf_token=csrf_token,
        auth_secret=_required_secret(settings),
    )
    if identity is None:
        raise _error(401, "admin_session_required")
    if (action == "reject" and body.reason is None) or (
        action == "approve" and body.reason is not None
    ):
        raise _error(422, "decision_invalid")
    try:
        await decide_review(
            engine,
            ReviewDecision(
                review_id, body.revision_id, identity.id, action, body.reason
            ),
        )
    except ModerationConflict as error:
        raise _error(409, str(error)) from error


@router.post("/events/special", response_model=CreatedSpecialResponse, status_code=201)
async def create_special(
    body: CreateSpecialRequest,
    request: Request,
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    csrf_token: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
) -> CreatedSpecialResponse:
    settings, _, engine = _dependencies(request)
    _validate_admin_request(request, settings, require_origin=True)
    if session_token is None or csrf_token is None:
        raise _error(401, "admin_session_required")
    identity = await load_staff_mutation_session(
        engine,
        token=session_token,
        csrf_token=csrf_token,
        auth_secret=_required_secret(settings),
    )
    if identity is None:
        raise _error(401, "admin_session_required")
    if identity.role != "admin":
        raise _error(403, "admin_required")
    try:
        event_id = await create_special_event(
            engine,
            staff_id=identity.id,
            city_id=body.city_id,
            title=body.title,
            description=body.description,
            starts_at=body.starts_at,
            ends_at=body.ends_at,
            place=body.place,
            latitude=body.latitude,
            longitude=body.longitude,
        )
    except EventManagementError as error:
        raise _error(422, str(error)) from error
    return CreatedSpecialResponse(id=str(event_id))


@router.post("/events/special/{event_id}/cancel", status_code=204)
async def cancel_special(
    event_id: UUID,
    body: CancelSpecialRequest,
    request: Request,
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    csrf_token: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
) -> None:
    settings, _, engine = _dependencies(request)
    _validate_admin_request(request, settings, require_origin=True)
    if session_token is None or csrf_token is None:
        raise _error(401, "admin_session_required")
    identity = await load_staff_mutation_session(
        engine,
        token=session_token,
        csrf_token=csrf_token,
        auth_secret=_required_secret(settings),
    )
    if identity is None or identity.role != "admin":
        raise _error(403, "admin_required")
    try:
        await cancel_special_event(
            engine, event_id=event_id, staff_id=identity.id, reason=body.reason
        )
    except EventManagementConflict as error:
        raise _error(409, str(error)) from error


@router.get("/events/special")
async def special_events(
    request: Request,
    response: Response,
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> dict[str, object]:
    settings, _, engine = _dependencies(request)
    _validate_admin_request(request, settings)
    identity, _ = await _require_session(
        engine, session_token, _required_secret(settings)
    )
    if identity.role != "admin":
        raise _error(403, "admin_required")
    async with engine.connect() as connection:
        rows = (
            (
                await connection.execute(
                    text(
                        """
                    SELECT e.id,r.title,r.starts_at,r.ends_at,c.name AS city
                    FROM events.events e
                    JOIN events.event_revisions r ON r.id=e.approved_revision_id
                    JOIN discovery.cities c ON c.id=e.city_id
                    WHERE e.kind='special' AND e.lifecycle_status='published'
                    ORDER BY r.starts_at,e.id
                    """
                    )
                )
            )
            .mappings()
            .all()
        )
    return {"items": [dict(row) for row in rows]}


async def _require_session(
    engine: AsyncEngine,
    token: str | None,
    secret: bytes,
    *,
    rotate_csrf: bool = False,
) -> tuple[StaffIdentity, str | None]:
    if token is None:
        raise _error(401, "admin_session_required")
    if rotate_csrf:
        session = await load_staff_session(engine, token=token, auth_secret=secret)
        if session is None:
            raise _error(401, "admin_session_required")
        return session
    identity = await load_staff_read_session(engine, token=token, auth_secret=secret)
    if identity is None:
        raise _error(401, "admin_session_required")
    return identity, None


def _dependencies(request: Request) -> tuple[Settings, Redis, AsyncEngine]:
    return (
        cast(Settings, request.app.state.settings),
        cast(Redis, request.app.state.redis_client),
        cast(AsyncEngine, request.app.state.database_engine),
    )


def _validate_admin_request(
    request: Request,
    settings: Settings,
    *,
    require_origin: bool = False,
) -> str:
    expected_origin = str(settings.admin_base_url).rstrip("/")
    expected_host = settings.admin_base_url.host
    if request.headers.get("Host", "").split(":", 1)[0] != expected_host:
        raise _error(403, "invalid_admin_host")
    origin = request.headers.get("Origin")
    if (require_origin or origin is not None) and origin != expected_origin:
        raise _error(403, "invalid_admin_origin")
    return expected_origin


def _required_secret(settings: Settings) -> bytes:
    secret = settings.auth_secret()
    if secret is None or len(secret) < 32:
        raise _error(503, "admin_auth_unavailable")
    return secret


def _request_source(request: Request) -> str:
    return request.headers.get("X-Real-IP") or (
        request.client.host if request.client else "unknown"
    )


def _staff_response(identity: StaffIdentity) -> StaffResponse:
    return StaffResponse(login=identity.login, role=identity.role)


def _login_error() -> HTTPException:
    return _error(401, "admin_login_failed")


def _error(status_code: int, code: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": "Admin authentication failed"},
    )
