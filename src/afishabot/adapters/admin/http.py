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
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from afishabot.adapters.tasks.celery_app import estimate_storage_savings_task
from afishabot.core.config import Settings
from afishabot.modules.discovery.application.street_anchors import (
    StreetAnchorError,
    create_staff_street_anchor_in_transaction,
    street_key,
)
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
from afishabot.modules.trust_safety.application.case_moderation import (
    CaseModerationError,
    decide_appeal,
    decide_case,
    moderation_counts,
    moderation_queue,
)
from afishabot.modules.trust_safety.application.case_moderation import (
    case_detail as moderation_case_detail,
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


class CaseDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["dismiss", "hide_component", "hold_for_correction", "hide_subject"]
    subject_component: str | None = Field(default=None, max_length=32)
    staff_note: str = Field(min_length=2, max_length=1000)
    expected_version: int = Field(ge=1)


class AppealDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["upheld", "reversed"]
    staff_note: str = Field(min_length=2, max_length=1000)
    expected_version: int = Field(ge=1)
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


class NewStreetAnchorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str = Field(min_length=1, max_length=200)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class StreetAnchorCreateRequest(NewStreetAnchorRequest):
    city_id: UUID


class StreetAnchorUpdateRequest(NewStreetAnchorRequest):
    geometry_version: int = Field(ge=1)


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
    street_anchor_id: UUID | None = None
    new_street_anchor: NewStreetAnchorRequest | None = None


class CancelSpecialRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: CancelReason


class CreateSpecialRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=60)
    description: str = Field(min_length=1, max_length=1000)
    city_id: UUID
    category_id: UUID
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


@router.get("/moderation/counts")
async def get_moderation_counts(
    request: Request,
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> dict[str, int]:
    settings, _, engine = _dependencies(request)
    _validate_admin_request(request, settings)
    await _require_session(engine, session_token, _required_secret(settings))
    return await moderation_counts(engine)


@router.get("/moderation/cases")
async def get_moderation_cases(
    request: Request,
    queue: Literal["reports", "appeals"],
    status: Literal["open"] = "open",
    cursor: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> dict[str, object]:
    del status
    settings, _, engine = _dependencies(request)
    _validate_admin_request(request, settings)
    await _require_session(engine, session_token, _required_secret(settings))
    rows = await moderation_queue(
        engine, queue=queue, limit=limit + 1, before=cursor
    )
    items = rows[:limit]
    next_cursor = None
    if len(rows) > limit and items:
        value = items[-1]["appeal_created_at"] or items[-1]["created_at"]
        next_cursor = value.isoformat()
    return {"items": items, "next_cursor": next_cursor}


@router.get("/moderation/cases/{case_public_id}")
async def get_moderation_case_detail(
    case_public_id: str,
    request: Request,
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> dict[str, object]:
    settings, _, engine = _dependencies(request)
    _validate_admin_request(request, settings)
    await _require_session(engine, session_token, _required_secret(settings))
    try:
        return await moderation_case_detail(engine, case_public_id)
    except CaseModerationError as error:
        raise _error(404, str(error)) from error


@router.get("/moderation/evidence/{case_public_id}")
async def get_moderation_case_evidence(
    case_public_id: str,
    request: Request,
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> Response:
    """Serve the immutable media referenced by a report to authenticated staff."""
    settings, _, engine = _dependencies(request)
    _validate_admin_request(request, settings)
    await _require_session(engine, session_token, _required_secret(settings))
    async with engine.connect() as connection:
        row = (
            (
                await connection.execute(
                    text("""
                    SELECT r.evidence_snapshot->>'component' AS component,
                           a.storage_key AS source_key,
                           (SELECT v.storage_key FROM media.asset_variants v
                            WHERE v.source_asset_id=a.id
                            ORDER BY CASE
                              WHEN v.variant_key IN ('avatar_256','background_768') THEN 0
                              ELSE 1
                            END,v.variant_key LIMIT 1) AS variant_key
                    FROM trust_safety.moderation_cases c
                    JOIN trust_safety.reports r ON r.case_id=c.id
                    JOIN media.assets a
                      ON a.id=CAST(r.evidence_snapshot->>'value' AS uuid)
                    WHERE c.public_id=:case
                      AND r.evidence_snapshot->>'component'
                          IN ('photo','avatar','background')
                    ORDER BY r.created_at LIMIT 1
                    """),
                    {"case": case_public_id},
                )
            )
            .mappings()
            .one_or_none()
        )
    if row is None:
        raise _error(404, "evidence_not_found")
    media_root = Path(settings.media_root).resolve()
    for storage_key in (row["variant_key"], row["source_key"]):
        if not storage_key:
            continue
        candidate = (media_root / storage_key).resolve()
        if candidate.is_relative_to(media_root) and candidate.is_file():
            return FileResponse(
                candidate,
                media_type="image/webp",
                headers={"Cache-Control": "private, no-store"},
            )
    raise _error(404, "evidence_file_not_found")


@router.post("/moderation/cases/{case_public_id}/decision", status_code=204)
async def post_moderation_case_decision(
    case_public_id: str,
    body: CaseDecisionRequest,
    request: Request,
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    csrf_token: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
    idempotency_key: Annotated[UUID | None, Header(alias="Idempotency-Key")] = None,
) -> None:
    settings, _, engine = _dependencies(request)
    _validate_admin_request(request, settings, require_origin=True)
    if session_token is None or csrf_token is None:
        raise _error(401, "admin_session_required")
    if idempotency_key is None:
        raise _error(400, "idempotency_key_required")
    identity = await load_staff_mutation_session(
        engine, token=session_token, csrf_token=csrf_token,
        auth_secret=_required_secret(settings)
    )
    if identity is None:
        raise _error(401, "admin_session_required")
    try:
        await decide_case(
            engine, public_id=case_public_id, actor_staff_id=identity.id,
            decision=body.decision, component=body.subject_component,
            staff_note=body.staff_note, expected_version=body.expected_version,
            idempotency_key=idempotency_key,
        )
    except CaseModerationError as error:
        code = str(error)
        conflict_codes = {
            "case_version_conflict",
            "case_evidence_stale",
            "subject_action_conflict",
        }
        raise _error(
            409 if code in conflict_codes else 422,
            code,
        ) from error
    except SQLAlchemyError as error:
        raise _error(503, "moderation_decision_unavailable") from error


@router.post("/moderation/cases/{case_public_id}/appeal-decision", status_code=204)
async def post_moderation_appeal_decision(
    case_public_id: str,
    body: AppealDecisionRequest,
    request: Request,
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    csrf_token: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
    idempotency_key: Annotated[UUID | None, Header(alias="Idempotency-Key")] = None,
) -> None:
    settings, _, engine = _dependencies(request)
    _validate_admin_request(request, settings, require_origin=True)
    if session_token is None or csrf_token is None:
        raise _error(401, "admin_session_required")
    if idempotency_key is None:
        raise _error(400, "idempotency_key_required")
    identity = await load_staff_mutation_session(
        engine, token=session_token, csrf_token=csrf_token,
        auth_secret=_required_secret(settings)
    )
    if identity is None:
        raise _error(401, "admin_session_required")
    try:
        await decide_appeal(
            engine, public_id=case_public_id, actor_staff_id=identity.id,
            decision=body.decision, staff_note=body.staff_note,
            expected_version=body.expected_version,
            idempotency_key=idempotency_key,
        )
    except CaseModerationError as error:
        code = str(error)
        raise _error(409 if code == "case_version_conflict" else 422, code) from error


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


@router.get("/street-anchors")
async def street_anchors(
    request: Request,
    response: Response,
    city_id: UUID,
    q: Annotated[str, Query(max_length=200)] = "",
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> dict[str, object]:
    settings, _, engine = _dependencies(request)
    _validate_admin_request(request, settings)
    await _require_session(engine, session_token, _required_secret(settings))
    async with engine.connect() as connection:
        rows = (await connection.execute(text("""
            SELECT a.id, a.city_id, a.display_name, a.source, a.geometry_version,
                   a.updated_at, ST_Y(a.anchor::geometry) AS latitude,
                   ST_X(a.anchor::geometry) AS longitude,
                   COUNT(r.id) FILTER (WHERE e.lifecycle_status='published'
                       AND r.ends_at > now())::int AS active_event_count
            FROM discovery.street_anchors a
            LEFT JOIN events.event_revisions r ON r.street_anchor_id=a.id
            LEFT JOIN events.events e ON e.id=r.event_id
            WHERE a.city_id=:city AND a.street_key LIKE :query
            GROUP BY a.id
            ORDER BY a.display_name
            LIMIT :limit
        """), {"city": city_id, "query": f"%{street_key(q)}%", "limit": limit})).mappings().all()
    response.headers["Cache-Control"] = "no-store"
    return {"items": [dict(row) for row in rows]}


@router.get("/street-anchors/{anchor_id}")
async def street_anchor_detail(
    anchor_id: UUID,
    request: Request,
    response: Response,
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> dict[str, object]:
    settings, _, engine = _dependencies(request)
    _validate_admin_request(request, settings)
    await _require_session(engine, session_token, _required_secret(settings))
    async with engine.connect() as connection:
        anchor = (await connection.execute(text("""
            SELECT a.id,a.city_id,c.name AS city,a.display_name,a.source,a.geometry_version,
                   a.updated_at,ST_Y(a.anchor::geometry) AS latitude,ST_X(a.anchor::geometry) AS longitude
            FROM discovery.street_anchors a JOIN discovery.cities c ON c.id=a.city_id
            WHERE a.id=:id
        """), {"id": anchor_id})).mappings().one_or_none()
        if anchor is None:
            raise _error(404, "street_anchor_not_found")
        events = (await connection.execute(text("""
            SELECT e.id, r.title, r.starts_at
            FROM events.event_revisions r JOIN events.events e ON e.id=r.event_id
            WHERE r.street_anchor_id=:id AND e.lifecycle_status='published' AND r.ends_at > now()
            ORDER BY r.starts_at
        """), {"id": anchor_id})).mappings().all()
    response.headers["Cache-Control"] = "no-store"
    return {**dict(anchor), "events": [dict(row) for row in events]}


@router.post("/street-anchors", status_code=201)
async def create_street_anchor(
    body: StreetAnchorCreateRequest, request: Request,
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    csrf_token: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
) -> dict[str, str]:
    settings, _, engine = _dependencies(request); _validate_admin_request(request, settings, require_origin=True)
    if session_token is None or csrf_token is None: raise _error(401, "admin_session_required")
    identity = await load_staff_mutation_session(engine, token=session_token, csrf_token=csrf_token, auth_secret=_required_secret(settings))
    if identity is None: raise _error(401, "admin_session_required")
    try:
        async with engine.begin() as connection:
            anchor_id = await create_staff_street_anchor_in_transaction(connection, city_id=body.city_id, display_name=body.display_name, latitude=body.latitude, longitude=body.longitude)
            await connection.execute(text("""INSERT INTO trust_safety.staff_audit_log
              (id,actor_staff_id,action,result,details) VALUES (gen_random_uuid(),:staff,'street_anchor.create','success',jsonb_build_object('street_anchor_id',CAST(:anchor AS text)))"""), {"staff": identity.id, "anchor": str(anchor_id)})
    except StreetAnchorError as error: raise _error(409 if str(error)=="street_anchor_exists" else 422, str(error)) from error
    return {"id": str(anchor_id)}


@router.patch("/street-anchors/{anchor_id}", status_code=204)
async def update_street_anchor(
    anchor_id: UUID, body: StreetAnchorUpdateRequest, request: Request,
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    csrf_token: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
) -> None:
    settings, _, engine = _dependencies(request); _validate_admin_request(request, settings, require_origin=True)
    if session_token is None or csrf_token is None: raise _error(401, "admin_session_required")
    identity = await load_staff_mutation_session(engine, token=session_token, csrf_token=csrf_token, auth_secret=_required_secret(settings))
    if identity is None: raise _error(401, "admin_session_required")
    key = street_key(body.display_name)
    async with engine.begin() as connection:
        row = await connection.scalar(text("""
          UPDATE discovery.street_anchors a SET display_name=:name,street_key=:key,
            anchor=ST_SetSRID(ST_Point(:longitude,:latitude),4326)::geography,
            source='staff',geometry_version=geometry_version+1,updated_at=now()
          FROM discovery.cities c WHERE a.id=:id AND c.id=a.city_id
            AND a.geometry_version=:version AND ST_DWithin(c.boundary,
              ST_SetSRID(ST_Point(:longitude,:latitude),4326)::geography,:radius)
          RETURNING a.id
        """), {"id": anchor_id,"name":body.display_name.strip(),"key":key,"latitude":body.latitude,"longitude":body.longitude,"version":body.geometry_version,"radius":1000})
        if row is None: raise _error(409, "street_anchor_stale_or_outside_city")
        await connection.execute(text("""INSERT INTO trust_safety.staff_audit_log
          (id,actor_staff_id,action,result,details) VALUES (gen_random_uuid(),:staff,'street_anchor.update','success',jsonb_build_object('street_anchor_id',CAST(:anchor AS text)))"""), {"staff":identity.id,"anchor":str(anchor_id)})


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
                review_id, body.revision_id, identity.id, action, body.reason,
                body.street_anchor_id,
                (body.new_street_anchor.display_name, body.new_street_anchor.latitude,
                 body.new_street_anchor.longitude)
                if body.new_street_anchor else None,
            ),
        )
    except ModerationConflict as error:
        raise _error(409, str(error)) from error


@router.post(
    "/events/community", response_model=CreatedSpecialResponse, status_code=201
)
@router.post(
    "/events/special",
    response_model=CreatedSpecialResponse,
    status_code=201,
    deprecated=True,
)
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
            category_id=body.category_id,
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
                    WHERE e.event_scope='community' AND e.lifecycle_status='published'
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
