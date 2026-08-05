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

from afishabot.core.config import Settings
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
    load_staff_session,
    load_staff_mutation_session,
    record_admin_event,
    revoke_staff_session,
)
from afishabot.modules.trust_safety.application.event_moderation import (
    ModerationConflict,
    ModerationNotFound,
    ReviewDecision,
    decide_review,
    review_detail,
    review_queue,
)
from afishabot.modules.events.application.manage_event import (
    CancelReason,
    EventManagementConflict,
    cancel_special_event,
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
    reason: Literal[
        "unclear_description", "prohibited_content", "paid_or_advertising",
        "inappropriate_photo", "invalid_place_or_time", "duplicate_or_spam",
    ] | None = None


class CancelSpecialRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: CancelReason


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
    bootstrap_cookie: Annotated[
        str | None, Cookie(alias=BOOTSTRAP_COOKIE)
    ] = None,
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
        engine, session_token, _required_secret(settings)
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
    _, csrf_token = await _require_session(
        engine, session_token, _required_secret(settings)
    )
    response.headers[CSRF_HEADER] = csrf_token
    response.headers["Cache-Control"] = "no-store"
    return DashboardResponse(**asdict(await dashboard_counts(engine)))


@router.get("/audit", response_model=AuditPageResponse)
async def audit(
    request: Request,
    response: Response,
    before: Annotated[datetime | None, Query()] = None,
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> AuditPageResponse:
    settings, _, engine = _dependencies(request)
    _validate_admin_request(request, settings)
    _, csrf_token = await _require_session(
        engine, session_token, _required_secret(settings)
    )
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
    response.headers[CSRF_HEADER] = csrf_token
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
    _, rotated = await _require_session(engine, session_token, _required_secret(settings))
    response.headers[CSRF_HEADER] = rotated
    rows = await review_queue(engine, offset=offset, limit=limit + 1)
    return {"items": rows[:limit], "next_offset": offset + limit if len(rows) > limit else None}


@router.get("/events/reviews/{review_id}")
async def event_review_detail(
    review_id: UUID, request: Request, response: Response,
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> dict[str, object]:
    settings, _, engine = _dependencies(request)
    _validate_admin_request(request, settings)
    _, rotated = await _require_session(engine, session_token, _required_secret(settings))
    try:
        detail = await review_detail(engine, review_id)
    except ModerationNotFound as error:
        raise _error(404, "review_not_found") from error
    detail["photo_url"] = f"/api/admin/events/reviews/{review_id}/photo"
    response.headers[CSRF_HEADER] = rotated
    return detail


@router.get("/events/reviews/{review_id}/photo")
async def event_review_photo(
    review_id: UUID, request: Request,
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> Response:
    settings, _, engine = _dependencies(request)
    _validate_admin_request(request, settings)
    await _require_session(engine, session_token, _required_secret(settings))
    try:
        detail = await review_detail(engine, review_id)
    except ModerationNotFound as error:
        raise _error(404, "review_not_found") from error
    path = Path(settings.media_root) / "event-staging" / f"{detail['media_asset_id']}.webp"
    if not path.is_file():
        raise _error(404, "photo_not_found")
    return FileResponse(path, media_type="image/webp", headers={"Cache-Control": "private, no-store"})


@router.post("/events/reviews/{review_id}/{action}", status_code=204)
async def decide_event_review(
    review_id: UUID, action: Literal["approve", "reject"],
    body: ReviewDecisionRequest, request: Request,
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    csrf_token: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
) -> None:
    settings, _, engine = _dependencies(request)
    _validate_admin_request(request, settings, require_origin=True)
    if session_token is None or csrf_token is None:
        raise _error(401, "admin_session_required")
    identity = await load_staff_mutation_session(
        engine, token=session_token, csrf_token=csrf_token,
        auth_secret=_required_secret(settings),
    )
    if identity is None:
        raise _error(401, "admin_session_required")
    if (action == "reject" and body.reason is None) or (
        action == "approve" and body.reason is not None
    ):
        raise _error(422, "decision_invalid")
    try:
        await decide_review(engine, ReviewDecision(review_id, body.revision_id, identity.id, action, body.reason))
    except ModerationConflict as error:
        raise _error(409, str(error)) from error


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
        engine, token=session_token, csrf_token=csrf_token,
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
    identity, rotated = await _require_session(
        engine, session_token, _required_secret(settings)
    )
    if identity.role != "admin":
        raise _error(403, "admin_required")
    async with engine.connect() as connection:
        rows = (
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
        ).mappings().all()
    response.headers[CSRF_HEADER] = rotated
    return {"items": [dict(row) for row in rows]}


async def _require_session(
    engine: AsyncEngine,
    token: str | None,
    secret: bytes,
) -> tuple[StaffIdentity, str]:
    if token is None:
        raise _error(401, "admin_session_required")
    session = await load_staff_session(engine, token=token, auth_secret=secret)
    if session is None:
        raise _error(401, "admin_session_required")
    return session


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
