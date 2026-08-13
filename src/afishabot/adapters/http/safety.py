"""User-facing reports and safe moderation case projections."""
# ruff: noqa: E501

import json
from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Cookie, Header, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from afishabot.adapters.http.auth import CSRF_HEADER, SESSION_COOKIE
from afishabot.adapters.http.profiles import (
    current_user,
    dependencies,
    mutation_user,
    validate_origin,
)

router = APIRouter(tags=["safety"])
SubjectType = Literal[
    "event", "profile", "looking_post", "q_and_a_answer", "chat_message"
]
SubjectComponent = Literal[
    "photo",
    "title",
    "description",
    "schedule",
    "location",
    "whole",
    "avatar",
    "background",
    "bio",
    "display_name",
    "body",
    "answer",
    "message",
]

ALLOWED_COMPONENTS: dict[str, set[str]] = {
    "event": {"photo", "title", "description", "schedule", "location", "whole"},
    "profile": {"avatar", "background", "bio", "display_name", "whole"},
    "looking_post": {"title", "body", "whole"},
    "q_and_a_answer": {"answer"},
    "chat_message": {"message"},
}


class ReportBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject_type: SubjectType
    subject_id: str = Field(min_length=1, max_length=64)
    reason_code: str = Field(min_length=2, max_length=64, pattern=r"^[a-z0-9_]+$")
    explanation: str | None = Field(default=None, max_length=500)
    subject_component: SubjectComponent | None = None


class AppealBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    explanation: str = Field(min_length=1, max_length=500)


def _public_id() -> str:
    return f"PV-{uuid4().hex[:8].upper()}"


async def _resolve_subject(
    connection: AsyncConnection, subject_type: SubjectType, raw_id: str
) -> dict[str, Any] | None:
    if subject_type == "profile":
        row = (
            (
                await connection.execute(
                    text(
                        "SELECT user_id AS id,user_id AS owner,false AS community FROM accounts.profiles WHERE public_id=:id"
                    ),
                    {"id": raw_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        return dict(row) if row else None
    try:
        subject_id = UUID(raw_id)
    except ValueError as error:
        raise HTTPException(status_code=422, detail="subject_id_invalid") from error
    statements = {
        "event": "SELECT id,creator_user_id AS owner,event_scope='community' AS community FROM events.events WHERE id=:id AND lifecycle_status<>'hidden'",
        "looking_post": "SELECT id,author_user_id AS owner,false AS community FROM discovery.looking_posts WHERE id=:id AND status<>'hidden'",
        "q_and_a_answer": "SELECT q.id,p.author_user_id AS owner,false AS community FROM discovery.looking_post_questions q JOIN discovery.looking_posts p ON p.id=q.looking_post_id WHERE q.id=:id AND q.answer IS NOT NULL AND q.answer_hidden_at IS NULL",
        "chat_message": "SELECT m.id,m.author_user_id AS owner,false AS community FROM communication.messages m JOIN events.events e ON e.id=m.event_id WHERE m.id=:id AND m.hidden_at IS NULL AND m.delete_after>now()",
    }
    row = (
        (await connection.execute(text(statements[subject_type]), {"id": subject_id}))
        .mappings()
        .one_or_none()
    )
    return dict(row) if row else None


async def _capture_evidence(
    connection: AsyncConnection,
    subject_type: SubjectType,
    subject_id: UUID,
    component: str,
) -> dict[str, Any]:
    """Capture immutable, bounded evidence before the reported content can change."""
    queries = {
        "event": """
          SELECT e.version,r.title,r.description,r.starts_at,r.ends_at,
                 COALESCE(r.organizer_address,r.normalized_address) AS location,
                 ep.media_asset_id AS photo_asset_id,p.display_name AS owner_name
          FROM events.events e
          JOIN events.event_revisions r ON r.id=COALESCE(e.approved_revision_id,e.current_revision_id)
          LEFT JOIN events.event_photos ep ON ep.revision_id=r.id AND ep.position=1
          LEFT JOIN accounts.profiles p ON p.user_id=e.creator_user_id WHERE e.id=:id
        """,
        "profile": """
          SELECT version,public_id,display_name,bio,avatar_asset_id,background_asset_id,
                 display_name AS owner_name FROM accounts.profiles WHERE user_id=:id
        """,
        "looking_post": """
          SELECT p.version,p.title,p.body,pr.display_name AS owner_name
          FROM discovery.looking_posts p LEFT JOIN accounts.profiles pr
            ON pr.user_id=p.author_user_id WHERE p.id=:id
        """,
        "q_and_a_answer": """
          SELECT 1 AS version,q.answer,p.title AS context_title,pr.display_name AS owner_name
          FROM discovery.looking_post_questions q JOIN discovery.looking_posts p
            ON p.id=q.looking_post_id LEFT JOIN accounts.profiles pr
            ON pr.user_id=p.author_user_id WHERE q.id=:id
        """,
        "chat_message": """
          SELECT 1 AS version,m.body AS message,e.id AS event_id,r.title AS context_title,
                 pr.display_name AS owner_name
          FROM communication.messages m JOIN events.events e ON e.id=m.event_id
          JOIN events.event_revisions r ON r.id=e.approved_revision_id
          LEFT JOIN accounts.profiles pr ON pr.user_id=m.author_user_id WHERE m.id=:id
        """,
    }
    row = (
        (await connection.execute(text(queries[subject_type]), {"id": subject_id}))
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="subject_not_found")
    data = dict(row)
    value_map: dict[str, object | None] = {
        "photo": data.get("photo_asset_id"),
        "avatar": data.get("avatar_asset_id"),
        "background": data.get("background_asset_id"),
        "title": data.get("title"),
        "description": data.get("description"),
        "body": data.get("body"),
        "bio": data.get("bio"),
        "display_name": data.get("display_name"),
        "answer": data.get("answer"),
        "message": data.get("message"),
        "schedule": f"{data.get('starts_at')} — {data.get('ends_at')}",
        "location": data.get("location"),
        "whole": data.get("title") or data.get("display_name"),
    }
    value = value_map.get(component)
    return {
        "schema_version": 1,
        "subject_type": subject_type,
        "component": component,
        "value": str(value) if value is not None else None,
        "object_version": int(data.get("version") or 1),
        "owner_name": data.get("owner_name"),
        "context_title": data.get("context_title"),
        "captured_at": datetime.now(UTC).isoformat(),
    }


@router.post("/safety/reports", status_code=201)
async def create_report(
    body: ReportBody,
    request: Request,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    csrf: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
    idempotency_key: Annotated[UUID | None, Header(alias="Idempotency-Key")] = None,
) -> dict[str, str]:
    settings, _, engine = dependencies(request)
    validate_origin(request, settings)
    reporter = await mutation_user(request, token, csrf)
    if idempotency_key is None:
        raise HTTPException(status_code=400, detail="idempotency_key_required")
    async with engine.begin() as connection:
        previous = (
            (
                await connection.execute(
                    text("""
          SELECT c.public_id,c.status FROM trust_safety.reports r
          JOIN trust_safety.moderation_cases c ON c.id=r.case_id
          WHERE r.reporter_user_id=:reporter AND r.idempotency_key=:key
        """),
                    {"reporter": reporter, "key": idempotency_key},
                )
            )
            .mappings()
            .one_or_none()
        )
        if previous:
            return {
                "case_public_id": previous["public_id"],
                "status": previous["status"],
            }
        subject = await _resolve_subject(connection, body.subject_type, body.subject_id)
        if subject is None:
            raise HTTPException(status_code=404, detail="subject_not_found")
        if subject["community"]:
            raise HTTPException(status_code=422, detail="report_not_allowed")
        if subject["owner"] == reporter:
            raise HTTPException(status_code=422, detail="cannot_report_self")
        component = body.subject_component or "whole"
        if component not in ALLOWED_COMPONENTS[body.subject_type]:
            raise HTTPException(status_code=422, detail="subject_component_invalid")
        duplicate = (
            (
                await connection.execute(
                    text("""
          SELECT c.id,c.public_id,c.status FROM trust_safety.moderation_cases c
          JOIN trust_safety.reports r ON r.case_id=c.id
          WHERE r.reporter_user_id=:reporter AND c.subject_type=:type
            AND c.subject_id=:subject AND c.subject_component=:component
            AND r.reason_code=:reason AND c.status<>'resolved'
          ORDER BY c.created_at DESC LIMIT 1
        """),
                    {
                        "reporter": reporter,
                        "type": body.subject_type,
                        "subject": subject["id"],
                        "component": component,
                        "reason": body.reason_code,
                    },
                )
            )
            .mappings()
            .one_or_none()
        )
        if duplicate:
            return {
                "case_public_id": duplicate["public_id"],
                "status": duplicate["status"],
            }
        evidence = await _capture_evidence(
            connection, body.subject_type, subject["id"], component
        )
        case_id, report_id, public_id = uuid4(), uuid4(), _public_id()
        await connection.execute(
            text("""
          INSERT INTO trust_safety.moderation_cases
            (id,public_id,subject_type,subject_id,subject_owner_user_id,subject_component)
          VALUES (:id,:public,:type,:subject,:owner,:component)
        """),
            {
                "id": case_id,
                "public": public_id,
                "type": body.subject_type,
                "subject": subject["id"],
                "owner": subject["owner"],
                "component": component,
            },
        )
        await connection.execute(
            text("""
          INSERT INTO trust_safety.reports
            (id,case_id,reporter_user_id,reason_code,explanation,idempotency_key,evidence_snapshot)
          VALUES (:id,:case,:reporter,:reason,:explanation,:key,CAST(:evidence AS jsonb))
        """),
            {
                "id": report_id,
                "case": case_id,
                "reporter": reporter,
                "reason": body.reason_code,
                "explanation": body.explanation,
                "key": idempotency_key,
                "evidence": json.dumps(evidence) if evidence else None,
            },
        )
        await connection.execute(
            text("""
          INSERT INTO trust_safety.case_timeline_entries
            (id,case_id,event_type,public_label) VALUES (:id,:case,'received','Обращение получено')
        """),
            {"id": uuid4(), "case": case_id},
        )
    return {"case_public_id": public_id, "status": "received"}


@router.get("/account/cases")
async def cases_feed(
    request: Request,
    status: Annotated[Literal["active", "resolved"], Query()] = "active",
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> dict[str, object]:
    user_id = await current_user(request, token)
    _, _, engine = dependencies(request)
    open_appeal = "EXISTS (SELECT 1 FROM trust_safety.appeals a WHERE a.case_id=c.id AND a.status IN ('submitted','reviewing'))"
    condition = (
        f"c.status='resolved' AND NOT {open_appeal}"
        if status == "resolved"
        else f"(c.status<>'resolved' OR {open_appeal})"
    )
    async with engine.connect() as connection:
        rows = (
            (
                await connection.execute(
                    text(f"""
          SELECT c.public_id,c.subject_type,c.status,c.created_at,c.updated_at
          FROM trust_safety.moderation_cases c
          WHERE (
            c.subject_owner_user_id=:user OR EXISTS (
              SELECT 1 FROM trust_safety.reports r
              WHERE r.case_id=c.id AND r.reporter_user_id=:user
            )
          ) AND {condition}
          ORDER BY c.updated_at DESC,c.id DESC LIMIT 50
        """),
                    {"user": user_id},
                )
            )
            .mappings()
            .all()
        )
    return {"items": [dict(row) for row in rows], "next_cursor": None}


@router.get("/account/cases/{case_public_id}")
async def case_detail(
    case_public_id: str,
    request: Request,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> dict[str, object]:
    user_id = await current_user(request, token)
    _, _, engine = dependencies(request)
    async with engine.connect() as connection:
        case = (
            (
                await connection.execute(
                    text("""
          SELECT DISTINCT c.id,c.public_id,c.subject_type,c.status,c.created_at,c.resolved_at,c.appeal_deadline,
            EXISTS(SELECT 1 FROM trust_safety.reports r2 WHERE r2.case_id=c.id AND r2.reporter_user_id=:user) AS is_reporter,
            c.subject_owner_user_id=:user AS is_subject_owner
          FROM trust_safety.moderation_cases c LEFT JOIN trust_safety.reports r ON r.case_id=c.id
          WHERE c.public_id=:public AND (r.reporter_user_id=:user OR c.subject_owner_user_id=:user)
        """),
                    {"public": case_public_id, "user": user_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        if case is None:
            raise HTTPException(status_code=404, detail="case_not_found")
        appeal = (
            (await connection.execute(text("SELECT status,explanation,created_at,decided_at FROM trust_safety.appeals WHERE case_id=:case"), {"case": case["id"]}))
            .mappings().one_or_none()
        )
        sanction = (
            (await connection.execute(text("SELECT status FROM trust_safety.moderation_sanctions WHERE case_id=:case"), {"case": case["id"]}))
            .mappings().one_or_none()
        )
        timeline = (
            (
                await connection.execute(
                    text("""
          SELECT event_type,public_label,created_at FROM trust_safety.case_timeline_entries
          WHERE case_id=:case ORDER BY created_at,id
        """),
                    {"case": case["id"]},
                )
            )
            .mappings()
            .all()
        )
    result = dict(case)
    result.pop("id", None)
    result["timeline"] = [dict(row) for row in timeline]
    result["appeal"] = dict(appeal) if appeal else None
    result["restoration_state"] = (
        ("pending" if sanction and sanction["status"] == "active" else sanction["status"])
        if sanction else "not_applicable"
    )
    if appeal:
        result["appeal_state"] = appeal["status"]
    elif not case["is_subject_owner"] or not case["appeal_deadline"]:
        result["appeal_state"] = "unavailable"
    elif datetime.now(UTC) > case["appeal_deadline"]:
        result["appeal_state"] = "expired"
    else:
        result["appeal_state"] = "available"
    result["can_appeal"] = bool(
        case["is_subject_owner"]
        and case["appeal_deadline"]
        and datetime.now(UTC) <= case["appeal_deadline"]
        and appeal is None
    )
    return result


@router.post("/account/cases/{case_public_id}/appeal", status_code=201)
async def appeal_case(
    case_public_id: str,
    body: AppealBody,
    request: Request,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    csrf: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
) -> dict[str, str]:
    settings, _, engine = dependencies(request)
    validate_origin(request, settings)
    user_id = await mutation_user(request, token, csrf)
    async with engine.begin() as connection:
        case = (
            (
                await connection.execute(
                    text("""
          SELECT id,resolved_at,appeal_deadline FROM trust_safety.moderation_cases
          WHERE public_id=:public AND subject_owner_user_id=:user AND status='resolved' FOR UPDATE
        """),
                    {"public": case_public_id, "user": user_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        if case is None:
            raise HTTPException(status_code=404, detail="case_not_found")
        if (
            case["appeal_deadline"] is None
            or datetime.now(UTC) > case["appeal_deadline"]
        ):
            raise HTTPException(status_code=409, detail="appeal_window_closed")
        exists = await connection.scalar(
            text(
                "SELECT 1 FROM trust_safety.appeals WHERE case_id=:case AND appellant_user_id=:user"
            ),
            {"case": case["id"], "user": user_id},
        )
        if exists:
            raise HTTPException(status_code=409, detail="appeal_already_submitted")
        await connection.execute(
            text("""
          INSERT INTO trust_safety.appeals(id,case_id,appellant_user_id,explanation)
          VALUES (:id,:case,:user,:explanation)
        """),
            {
                "id": uuid4(),
                "case": case["id"],
                "user": user_id,
                "explanation": body.explanation,
            },
        )
        await connection.execute(
            text("""
          INSERT INTO trust_safety.case_timeline_entries(id,case_id,event_type,public_label)
          VALUES (:id,:case,'appeal_submitted','Апелляция отправлена')
        """),
            {"id": uuid4(), "case": case["id"]},
        )
    return {"status": "submitted"}
