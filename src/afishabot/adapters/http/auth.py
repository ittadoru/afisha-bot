from dataclasses import asdict
from typing import Annotated, cast

from fastapi import APIRouter, Cookie, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from afishabot.core.config import Settings
from afishabot.modules.accounts.application.auth import (
    AccountProfile,
    confirm_age,
    resolve_identity_and_issue_session,
    revoke_session,
    rotate_session_csrf,
)
from afishabot.modules.accounts.domain.telegram_auth import (
    TelegramAuthError,
    verify_telegram_init_data,
)
from afishabot.modules.accounts.infrastructure.auth_guard import (
    AuthGuardDenied,
    AuthGuardUnavailable,
    create_bootstrap,
    consume_bootstrap_and_claim_payload,
    protected_digest,
)

router = APIRouter(tags=["account"])

SESSION_COOKIE = "afisha_mini_session"
BOOTSTRAP_COOKIE = "afisha_mini_bootstrap"
CSRF_HEADER = "X-Afisha-CSRF"


class ExchangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    init_data: str = Field(min_length=1, max_length=8192)
    nonce: str = Field(min_length=32, max_length=128)


class ProfileResponse(BaseModel):
    public_id: str
    display_name: str
    bio: str | None
    selected_city_id: str | None
    age_confirmed: bool


class SessionResponse(BaseModel):
    profile: ProfileResponse
    csrf_token: str
    created: bool


class BootstrapResponse(BaseModel):
    nonce: str


@router.post("/auth/mini/bootstrap", response_model=BootstrapResponse)
async def bootstrap(request: Request, response: Response) -> BootstrapResponse:
    settings, redis, _ = _dependencies(request)
    origin = _validated_origin(request, settings)
    auth_secret = _required_auth_secret(settings)
    client_address = request.headers.get("X-Real-IP") or (
        request.client.host if request.client else "unknown"
    )
    fingerprint = protected_digest(auth_secret, client_address)
    try:
        proof = await create_bootstrap(
            redis,
            origin=origin,
            request_fingerprint=fingerprint,
            auth_secret=auth_secret,
        )
    except AuthGuardDenied as error:
        raise _error(status.HTTP_429_TOO_MANY_REQUESTS, "auth_rate_limited") from error
    except AuthGuardUnavailable as error:
        raise _error(status.HTTP_503_SERVICE_UNAVAILABLE, "auth_unavailable") from error
    response.set_cookie(
        BOOTSTRAP_COOKIE,
        proof.cookie,
        max_age=300,
        secure=True,
        httponly=True,
        samesite="strict",
        path="/api/auth/mini",
    )
    response.headers["Cache-Control"] = "no-store"
    return BootstrapResponse(nonce=proof.nonce)


@router.post("/auth/mini/exchange", response_model=SessionResponse)
async def exchange(
    body: ExchangeRequest,
    request: Request,
    response: Response,
    bootstrap_cookie: Annotated[str | None, Cookie(alias=BOOTSTRAP_COOKIE)] = None,
) -> SessionResponse:
    settings, redis, engine = _dependencies(request)
    origin = _validated_origin(request, settings)
    bot_token = settings.bot_token()
    auth_secret = _required_auth_secret(settings)
    if bot_token is None or bootstrap_cookie is None:
        raise _error(status.HTTP_503_SERVICE_UNAVAILABLE, "auth_unavailable")
    try:
        telegram_user = verify_telegram_init_data(body.init_data, bot_token)
        await consume_bootstrap_and_claim_payload(
            redis,
            nonce=body.nonce,
            cookie=bootstrap_cookie,
            origin=origin,
            payload_digest=telegram_user.payload_digest,
            auth_secret=auth_secret,
        )
    except TelegramAuthError as error:
        raise _error(status.HTTP_401_UNAUTHORIZED, "invalid_telegram_auth") from error
    except AuthGuardDenied as error:
        raise _error(status.HTTP_409_CONFLICT, "auth_replayed") from error
    except AuthGuardUnavailable as error:
        raise _error(status.HTTP_503_SERVICE_UNAVAILABLE, "auth_unavailable") from error

    session = await resolve_identity_and_issue_session(
        engine,
        telegram_user_id=telegram_user.telegram_user_id,
        auth_secret=auth_secret,
    )
    response.delete_cookie(BOOTSTRAP_COOKIE, path="/api/auth/mini")
    response.set_cookie(
        SESSION_COOKIE,
        session.token,
        max_age=24 * 60 * 60,
        secure=True,
        httponly=True,
        samesite="strict",
        path="/api",
    )
    response.headers["Cache-Control"] = "no-store"
    return SessionResponse(
        profile=_profile_response(session.profile),
        csrf_token=session.csrf_token,
        created=session.created,
    )


@router.get("/account/me", response_model=ProfileResponse)
async def me(
    request: Request,
    response: Response,
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> ProfileResponse:
    settings, _, engine = _dependencies(request)
    if session_token is None:
        raise _error(status.HTTP_401_UNAUTHORIZED, "session_required")
    session = await rotate_session_csrf(
        engine,
        token=session_token,
        auth_secret=_required_auth_secret(settings),
    )
    if session is None:
        raise _error(status.HTTP_401_UNAUTHORIZED, "invalid_session")
    profile, csrf_token = session
    response.headers[CSRF_HEADER] = csrf_token
    response.headers["Cache-Control"] = "no-store"
    return _profile_response(profile)


@router.post("/account/age-consent", response_model=ProfileResponse)
async def age_consent(
    request: Request,
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    csrf_token: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
) -> ProfileResponse:
    settings, _, engine = _dependencies(request)
    if session_token is None or csrf_token is None:
        raise _error(status.HTTP_401_UNAUTHORIZED, "session_required")
    profile = await confirm_age(
        engine,
        token=session_token,
        csrf_token=csrf_token,
        auth_secret=_required_auth_secret(settings),
    )
    if profile is None:
        raise _error(status.HTTP_401_UNAUTHORIZED, "invalid_session_or_csrf")
    return _profile_response(profile)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    csrf_token: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
) -> None:
    settings, _, engine = _dependencies(request)
    if session_token is None or csrf_token is None:
        raise _error(status.HTTP_401_UNAUTHORIZED, "session_required")
    revoked = await revoke_session(
        engine,
        token=session_token,
        csrf_token=csrf_token,
        auth_secret=_required_auth_secret(settings),
    )
    if not revoked:
        raise _error(status.HTTP_401_UNAUTHORIZED, "invalid_session_or_csrf")
    response.delete_cookie(SESSION_COOKIE, path="/api")


def _dependencies(request: Request) -> tuple[Settings, Redis, AsyncEngine]:
    return (
        cast(Settings, request.app.state.settings),
        cast(Redis, request.app.state.redis_client),
        cast(AsyncEngine, request.app.state.database_engine),
    )


def _validated_origin(request: Request, settings: Settings) -> str:
    origin = request.headers.get("Origin")
    expected = str(settings.public_base_url).rstrip("/")
    if origin != expected:
        raise _error(status.HTTP_403_FORBIDDEN, "invalid_origin")
    return origin


def _required_auth_secret(settings: Settings) -> bytes:
    value = settings.auth_secret()
    if value is None or len(value) < 32:
        raise _error(status.HTTP_503_SERVICE_UNAVAILABLE, "auth_unavailable")
    return value


def _profile_response(profile: AccountProfile) -> ProfileResponse:
    values = asdict(profile)
    values.pop("user_id")
    values["selected_city_id"] = (
        None if profile.selected_city_id is None else str(profile.selected_city_id)
    )
    return ProfileResponse.model_validate(values)


def _error(status_code: int, code: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": "Authentication failed"},
    )
