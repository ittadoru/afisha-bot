from dataclasses import asdict
from datetime import datetime
from typing import Annotated, cast

from fastapi import APIRouter, Cookie, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from redis.asyncio import Redis
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


class AuditEntryResponse(BaseModel):
    id: str
    created_at: datetime
    actor: str | None
    action: str
    result: str


class AuditPageResponse(BaseModel):
    items: list[AuditEntryResponse]
    next_before: datetime | None


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
