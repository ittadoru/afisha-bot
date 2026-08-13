"""Staff moderation queues, immutable decisions and profile sanctions."""
# ruff: noqa: E501

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal, cast
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

QueueName = Literal["reports", "appeals"]
Decision = Literal["dismiss", "hide_component", "hold_for_correction", "hide_subject"]
AppealDecision = Literal["upheld", "reversed"]
ProfileComponent = Literal["avatar", "background", "bio", "display_name"]


class CaseModerationError(Exception):
    pass


def _direction(component: str | None) -> str | None:
    if component in {"avatar", "background"}:
        return "profile_media"
    if component in {"bio", "display_name"}:
        return "profile_text"
    return None


async def moderation_counts(engine: AsyncEngine) -> dict[str, int]:
    async with engine.connect() as connection:
        row = (
            (
                await connection.execute(
                    text("""
                    SELECT
                      (SELECT count(*) FROM trust_safety.event_reviews
                       WHERE status='pending') AS events,
                      (SELECT count(*) FROM trust_safety.moderation_cases
                       WHERE status<>'resolved') AS reports,
                      (SELECT count(*) FROM trust_safety.appeals
                       WHERE status IN ('submitted','reviewing')) AS appeals
                    """)
                )
            )
            .mappings()
            .one()
        )
    return {key: int(row[key]) for key in ("events", "reports", "appeals")}


async def moderation_queue(
    engine: AsyncEngine,
    *,
    queue: QueueName,
    limit: int,
    before: datetime | None = None,
) -> list[dict[str, Any]]:
    cursor_clause = ""
    parameters: dict[str, Any] = {"limit": limit}
    if before is not None:
        cursor_column = "a.created_at" if queue == "appeals" else "c.created_at"
        cursor_clause = f" AND {cursor_column}<:before"
        parameters["before"] = before
    if queue == "appeals":
        statement = f"""
          SELECT c.public_id,c.subject_type,c.subject_component,c.priority,c.version,
                 c.created_at,c.updated_at,r.reason_code,a.created_at AS appeal_created_at,
                 a.status AS appeal_status,
                 CASE c.subject_type
                   WHEN 'event' THEN (SELECT er.title FROM events.events e JOIN events.event_revisions er ON er.id=COALESCE(e.approved_revision_id,e.current_revision_id) WHERE e.id=c.subject_id)
                   WHEN 'profile' THEN (SELECT p.display_name FROM accounts.profiles p WHERE p.user_id=c.subject_id)
                   WHEN 'looking_post' THEN (SELECT p.title FROM discovery.looking_posts p WHERE p.id=c.subject_id)
                   WHEN 'q_and_a_answer' THEN (SELECT left(q.answer,80) FROM discovery.looking_post_questions q WHERE q.id=c.subject_id)
                   WHEN 'chat_message' THEN (SELECT left(m.body,80) FROM communication.messages m WHERE m.id=c.subject_id)
                 END AS target_title
          FROM trust_safety.appeals a
          JOIN trust_safety.moderation_cases c ON c.id=a.case_id
          LEFT JOIN LATERAL (
            SELECT reason_code FROM trust_safety.reports
            WHERE case_id=c.id ORDER BY created_at LIMIT 1
          ) r ON true
          WHERE a.status IN ('submitted','reviewing'){cursor_clause}
          ORDER BY a.created_at,c.id LIMIT :limit
        """
    else:
        statement = f"""
          SELECT c.public_id,c.subject_type,c.subject_component,c.priority,c.version,
                 c.created_at,c.updated_at,r.reason_code,NULL::timestamptz AS appeal_created_at,
                 NULL::varchar AS appeal_status,
                 CASE c.subject_type
                   WHEN 'event' THEN (SELECT er.title FROM events.events e JOIN events.event_revisions er ON er.id=COALESCE(e.approved_revision_id,e.current_revision_id) WHERE e.id=c.subject_id)
                   WHEN 'profile' THEN (SELECT p.display_name FROM accounts.profiles p WHERE p.user_id=c.subject_id)
                   WHEN 'looking_post' THEN (SELECT p.title FROM discovery.looking_posts p WHERE p.id=c.subject_id)
                   WHEN 'q_and_a_answer' THEN (SELECT left(q.answer,80) FROM discovery.looking_post_questions q WHERE q.id=c.subject_id)
                   WHEN 'chat_message' THEN (SELECT left(m.body,80) FROM communication.messages m WHERE m.id=c.subject_id)
                 END AS target_title
          FROM trust_safety.moderation_cases c
          LEFT JOIN LATERAL (
            SELECT reason_code FROM trust_safety.reports
            WHERE case_id=c.id ORDER BY created_at LIMIT 1
          ) r ON true
          WHERE c.status<>'resolved'{cursor_clause}
          ORDER BY CASE c.priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 ELSE 2 END,
                   c.created_at,c.id LIMIT :limit
        """
    async with engine.connect() as connection:
        rows = (await connection.execute(text(statement), parameters)).mappings().all()
    return [dict(row) for row in rows]


async def case_detail(engine: AsyncEngine, public_id: str) -> dict[str, Any]:
    async with engine.connect() as connection:
        case = (
            (
                await connection.execute(
                    text("""
                    SELECT c.id,c.public_id,c.subject_type,c.subject_id,c.subject_owner_user_id,c.subject_component,
                           c.status,c.priority,c.version,c.created_at,c.updated_at,
                           c.resolved_at,c.appeal_deadline,r.reason_code,r.explanation,
                           r.evidence_snapshot
                    FROM trust_safety.moderation_cases c
                    LEFT JOIN LATERAL (
                      SELECT reason_code,explanation,evidence_snapshot
                      FROM trust_safety.reports WHERE case_id=c.id ORDER BY created_at LIMIT 1
                    ) r ON true WHERE c.public_id=:public
                    """),
                    {"public": public_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        if case is None:
            raise CaseModerationError("case_not_found")
        subject = await _subject_projection(connection, dict(case))
        timeline = (
            (
                await connection.execute(
                    text("""
                    SELECT event_type,public_label,created_at
                    FROM trust_safety.case_timeline_entries WHERE case_id=:case
                    ORDER BY created_at,id
                    """),
                    {"case": case["id"]},
                )
            )
            .mappings()
            .all()
        )
        decisions = (
            (
                await connection.execute(
                    text("""
                    SELECT d.decision_type,d.subject_component,d.staff_note,d.created_at,
                           s.login AS actor
                    FROM trust_safety.case_decisions d
                    JOIN trust_safety.staff_accounts s ON s.id=d.actor_staff_id
                    WHERE d.case_id=:case ORDER BY d.created_at,d.id
                    """),
                    {"case": case["id"]},
                )
            )
            .mappings()
            .all()
        )
        appeal = (
            (
                await connection.execute(
                    text("""
                    SELECT status,explanation,created_at,decided_at
                    FROM trust_safety.appeals WHERE case_id=:case
                    """),
                    {"case": case["id"]},
                )
            )
            .mappings()
            .one_or_none()
        )
        direction = _direction(case["subject_component"])
        previous = 0
        if direction:
            previous = int(
                await connection.scalar(
                    text("""
                    SELECT count(*) FROM trust_safety.profile_violations
                    WHERE user_id=:user AND direction=:direction AND status='confirmed'
                      AND created_at>=now()-interval '180 days'
                    """),
                    {"user": case["subject_owner_user_id"], "direction": direction},
                )
                or 0
            )
    result = dict(case)
    result.pop("id", None)
    result.pop("subject_owner_user_id", None)
    result["subject"] = subject
    evidence = cast(dict[str, Any], case["evidence_snapshot"] or {})
    current_version = int((subject or {}).get("version") or 1)
    evidence_version = int(evidence.get("object_version") or 1)
    component = str(case["subject_component"] or "whole")
    result["target"] = {
        "subject_type": case["subject_type"],
        "component": component,
        "subject_id": str(case["subject_id"]),
        "title": (subject or {}).get("title")
        or (subject or {}).get("display_name")
        or evidence.get("context_title")
        or evidence.get("owner_name"),
        "owner_name": (subject or {}).get("owner_name") or evidence.get("owner_name"),
    }
    result["evidence"] = evidence
    result["current_state"] = subject
    result["evidence_state"] = (
        "changed" if current_version != evidence_version else "current"
    )
    result["available_actions"] = _available_actions(case["subject_type"], component)
    result["timeline"] = [dict(row) for row in timeline]
    result["decisions"] = [dict(row) for row in decisions]
    result["appeal"] = dict(appeal) if appeal else None
    result["previous_violations"] = previous
    return result


def _available_actions(subject_type: str, component: str) -> list[str]:
    if subject_type == "event":
        return ["dismiss", "hide_subject"]
    if subject_type == "looking_post":
        return [
            "dismiss",
            "hold_for_correction" if component != "whole" else "hide_subject",
        ]
    if subject_type in {"profile", "q_and_a_answer", "chat_message"}:
        return ["dismiss", "hide_subject" if component == "whole" else "hide_component"]
    return ["dismiss"]


async def _subject_projection(
    connection: AsyncConnection, case: dict[str, Any]
) -> dict[str, Any] | None:
    subject_type, subject_id = case["subject_type"], case["subject_id"]
    statements = {
        "event": """
            SELECT r.title,r.description,r.starts_at,r.ends_at,
                   COALESCE(r.organizer_address,r.normalized_address) AS location,
                   e.lifecycle_status AS status,e.version,p.display_name AS owner_name
            FROM events.events e
            LEFT JOIN events.event_revisions r
              ON r.id=COALESCE(e.approved_revision_id,e.current_revision_id)
            LEFT JOIN accounts.profiles p ON p.user_id=e.creator_user_id
            WHERE e.id=:id
        """,
        "looking_post": "SELECT p.title,p.body,p.status,p.version,pr.display_name AS owner_name FROM discovery.looking_posts p LEFT JOIN accounts.profiles pr ON pr.user_id=p.author_user_id WHERE p.id=:id",
        "q_and_a_answer": "SELECT q.answer,q.answer_hidden_at IS NOT NULL AS hidden,1 AS version,p.title,pr.display_name AS owner_name FROM discovery.looking_post_questions q JOIN discovery.looking_posts p ON p.id=q.looking_post_id LEFT JOIN accounts.profiles pr ON pr.user_id=p.author_user_id WHERE q.id=:id",
        "chat_message": "SELECT CASE WHEN m.hidden_at IS NULL THEN m.body ELSE 'Сообщение скрыто модерацией' END AS message,m.hidden_at IS NOT NULL AS hidden,1 AS version,r.title,pr.display_name AS owner_name FROM communication.messages m JOIN events.events e ON e.id=m.event_id JOIN events.event_revisions r ON r.id=e.approved_revision_id LEFT JOIN accounts.profiles pr ON pr.user_id=m.author_user_id WHERE m.id=:id",
        "profile": "SELECT public_id,display_name,bio,avatar_asset_id IS NOT NULL AS has_avatar,background_asset_id IS NOT NULL AS has_background,version,display_name AS owner_name FROM accounts.profiles WHERE user_id=:id",
    }
    statement = statements.get(subject_type)
    if statement is None:
        return {"type": subject_type, "available": False}
    try:
        async with connection.begin_nested():
            row = (
                (await connection.execute(text(statement), {"id": subject_id}))
                .mappings()
                .one_or_none()
            )
    except SQLAlchemyError:
        # A stale/deleted subject must not make the immutable case history
        # unavailable to staff. The captured evidence remains the fallback.
        return None
    return dict(row) if row else None


async def decide_case(
    engine: AsyncEngine,
    *,
    public_id: str,
    actor_staff_id: UUID,
    decision: Decision,
    component: str | None,
    staff_note: str,
    expected_version: int,
    idempotency_key: UUID,
) -> None:
    async with engine.begin() as connection:
        duplicate = await connection.scalar(
            text(
                "SELECT id FROM trust_safety.case_decisions WHERE idempotency_key=:key"
            ),
            {"key": idempotency_key},
        )
        if duplicate:
            return
        case = (
            (
                await connection.execute(
                    text("""
                    SELECT * FROM trust_safety.moderation_cases
                    WHERE public_id=:public FOR UPDATE
                    """),
                    {"public": public_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        if case is None:
            raise CaseModerationError("case_not_found")
        if case["status"] == "resolved" or case["version"] != expected_version:
            raise CaseModerationError("case_version_conflict")
        chosen = component or case["subject_component"]
        evidence = cast(
            dict[str, Any],
            await connection.scalar(
                text(
                    "SELECT evidence_snapshot FROM trust_safety.reports "
                    "WHERE case_id=:case ORDER BY created_at LIMIT 1"
                ),
                {"case": case["id"]},
            )
            or {},
        )
        if decision != "dismiss":
            report_version = int(
                await connection.scalar(
                    text(
                        "SELECT COALESCE((evidence_snapshot->>'object_version')::integer,1) "
                        "FROM trust_safety.reports WHERE case_id=:case ORDER BY created_at LIMIT 1"
                    ),
                    {"case": case["id"]},
                )
                or 1
            )
            current = await _current_subject_version(connection, dict(case))
            if current != report_version:
                raise CaseModerationError("case_evidence_stale")
            previous_state = await _sanction_state(connection, dict(case), chosen)
            await _apply_subject_action(connection, dict(case), chosen, decision)
            version_after = await _current_subject_version(connection, dict(case))
            await connection.execute(
                text("""
                  INSERT INTO trust_safety.moderation_sanctions
                    (id,case_id,decision_type,subject_component,subject_version_before,
                     subject_version_after,previous_state)
                  VALUES (:id,:case,:decision,:component,:before,:after,CAST(:state AS jsonb))
                """),
                {
                    "id": uuid4(), "case": case["id"], "decision": decision,
                    "component": chosen, "before": report_version,
                    "after": version_after,
                    "state": json.dumps(
                        {**previous_state, "evidence": evidence}, default=str
                    ),
                },
            )
        now = datetime.now(UTC)
        appeal_deadline = now + timedelta(days=3) if decision != "dismiss" else None
        await connection.execute(
            text("""
            INSERT INTO trust_safety.case_decisions
              (id,case_id,actor_staff_id,decision_type,subject_component,staff_note,
               idempotency_key,case_version)
            VALUES (:id,:case,:actor,:decision,:component,:note,:key,:version)
            """),
            {
                "id": uuid4(),
                "case": case["id"],
                "actor": actor_staff_id,
                "decision": decision,
                "component": chosen,
                "note": staff_note,
                "key": idempotency_key,
                "version": expected_version,
            },
        )
        await connection.execute(
            text("""
            UPDATE trust_safety.moderation_cases SET status='resolved',resolved_at=:now,
              appeal_deadline=:deadline,subject_component=COALESCE(:component,subject_component),
              version=version+1,updated_at=:now WHERE id=:id
            """),
            {
                "now": now,
                "deadline": appeal_deadline,
                "component": chosen,
                "id": case["id"],
            },
        )
        await connection.execute(
            text("""
            UPDATE trust_safety.profile_reports
            SET status=:status,decided_at=:now
            WHERE id=:id AND status IN ('pending','reviewed')
            """),
            {
                "status": "actioned" if decision != "dismiss" else "dismissed",
                "now": now,
                "id": case["id"],
            },
        )
        label = (
            "Нарушение подтверждено" if decision != "dismiss" else "Жалоба отклонена"
        )
        await _timeline(connection, case["id"], "resolved", label)
        direction = _direction(chosen) if case["subject_type"] == "profile" else None
        if decision != "dismiss" and direction:
            await connection.execute(
                text("""
                INSERT INTO trust_safety.profile_violations
                  (id,case_id,user_id,direction,confirm_after)
                VALUES (:id,:case,:user,:direction,:after)
                """),
                {
                    "id": uuid4(),
                    "case": case["id"],
                    "user": case["subject_owner_user_id"],
                    "direction": direction,
                    "after": appeal_deadline,
                },
            )
        if decision != "dismiss":
            await _notify_owner(
                connection, dict(case), chosen, decision, public_id, appeal_deadline
            )
            if case["subject_type"] == "event":
                await _notify_event_audience(
                    connection,
                    event_id=case["subject_id"],
                    case_id=case["id"],
                    kind="event_moderation_hidden",
                    title="Событие временно недоступно",
                    body="Событие скрыто на время апелляции организатора.",
                    business_suffix="hidden",
                )
        await _audit(connection, actor_staff_id, "case.decision", public_id, decision)


async def _current_subject_version(
    connection: AsyncConnection, case: dict[str, Any]
) -> int:
    table = {
        "event": "events.events",
        "profile": "accounts.profiles",
        "looking_post": "discovery.looking_posts",
    }.get(case["subject_type"])
    if table is None:
        return 1
    return int(
        await connection.scalar(
            text(
                f"SELECT version FROM {table} WHERE id=:id"
                if table != "accounts.profiles"
                else f"SELECT version FROM {table} WHERE user_id=:id"
            ),
            {"id": case["subject_id"]},
        )
        or 1
    )


async def _apply_subject_action(
    connection: AsyncConnection,
    case: dict[str, Any],
    component: str | None,
    decision: Decision,
) -> None:
    subject_type = case["subject_type"]
    result = None
    if subject_type == "event":
        if decision != "hide_subject":
            raise CaseModerationError("event_action_invalid")
        result = await connection.execute(
            text(
                "UPDATE events.events SET lifecycle_status='hidden',moderation_status='held',version=version+1,updated_at=now() WHERE id=:id"
            ),
            {"id": case["subject_id"]},
        )
    elif subject_type == "looking_post":
        result = await connection.execute(
            text(
                "UPDATE discovery.looking_posts SET status='hidden',closed_at=now(),"
                "delete_after=CASE WHEN :delete_subject THEN now()+interval '24 hours' "
                "ELSE NULL END,version=version+1 WHERE id=:id"
            ),
            {
                "id": case["subject_id"],
                "delete_subject": decision == "hide_subject",
            },
        )
    elif subject_type == "q_and_a_answer":
        result = await connection.execute(
            text(
                "UPDATE discovery.looking_post_questions SET answer_hidden_at=now(),answer_hidden_by_case_id=:case WHERE id=:id AND answer_hidden_at IS NULL"
            ),
            {"id": case["subject_id"], "case": case["id"]},
        )
    elif subject_type == "chat_message":
        result = await connection.execute(
            text(
                "UPDATE communication.messages SET hidden_at=now(),hidden_by_case_id=:case WHERE id=:id AND hidden_at IS NULL"
            ),
            {"id": case["subject_id"], "case": case["id"]},
        )
    elif subject_type == "profile":
        if decision == "hide_subject" and component == "whole":
            result = await connection.execute(
                text(
                    "UPDATE media.assets SET state='moderation_hidden',updated_at=now() "
                    "WHERE id IN (SELECT avatar_asset_id FROM accounts.profiles "
                    "WHERE user_id=:id UNION SELECT background_asset_id FROM "
                    "accounts.profiles WHERE user_id=:id)"
                ),
                {"id": case["subject_id"]},
            )
            result = await connection.execute(
                text(
                    "UPDATE accounts.profiles SET display_name='Пользователь',bio=NULL,"
                    "avatar_asset_id=NULL,background_asset_id=NULL,version=version+1,"
                    "updated_at=now() WHERE user_id=:id"
                ),
                {"id": case["subject_id"]},
            )
            if result.rowcount != 1:
                raise CaseModerationError("subject_action_conflict")
            return
        if component not in {"avatar", "background", "bio", "display_name"}:
            raise CaseModerationError("profile_component_required")
        if component == "avatar":
            await connection.execute(
                text(
                    "UPDATE media.assets SET state='moderation_hidden',updated_at=now() WHERE id=(SELECT avatar_asset_id FROM accounts.profiles WHERE user_id=:id)"
                ),
                {"id": case["subject_id"]},
            )
            statement = "UPDATE accounts.profiles SET avatar_asset_id=NULL,version=version+1,updated_at=now() WHERE user_id=:id"
        elif component == "background":
            await connection.execute(
                text(
                    "UPDATE media.assets SET state='moderation_hidden',updated_at=now() WHERE id=(SELECT background_asset_id FROM accounts.profiles WHERE user_id=:id)"
                ),
                {"id": case["subject_id"]},
            )
            statement = "UPDATE accounts.profiles SET background_asset_id=NULL,version=version+1,updated_at=now() WHERE user_id=:id"
        elif component == "bio":
            statement = "UPDATE accounts.profiles SET bio=NULL,version=version+1,updated_at=now() WHERE user_id=:id"
        else:
            statement = "UPDATE accounts.profiles SET display_name='Пользователь',display_name_changed_at=NULL,version=version+1,updated_at=now() WHERE user_id=:id"
        result = await connection.execute(text(statement), {"id": case["subject_id"]})
    else:
        raise CaseModerationError("subject_action_not_supported")
    if result is None or result.rowcount != 1:
        raise CaseModerationError("subject_action_conflict")


async def _sanction_state(
    connection: AsyncConnection, case: dict[str, Any], component: str | None
) -> dict[str, Any]:
    """Capture only values necessary to undo this exact action."""
    subject_type = case["subject_type"]
    if subject_type == "profile":
        row = await connection.execute(
            text("""SELECT display_name,bio,avatar_asset_id,background_asset_id,version
                    FROM accounts.profiles WHERE user_id=:id"""), {"id": case["subject_id"]}
        )
    elif subject_type == "event":
        row = await connection.execute(
            text("""SELECT lifecycle_status,moderation_status,version FROM events.events WHERE id=:id"""),
            {"id": case["subject_id"]},
        )
    elif subject_type == "looking_post":
        row = await connection.execute(
            text("""SELECT status,closed_at,delete_after,version FROM discovery.looking_posts WHERE id=:id"""),
            {"id": case["subject_id"]},
        )
    else:
        return {"component": component}
    value = row.mappings().one_or_none()
    return dict(value) if value else {"component": component}


async def _reverse_sanction(
    connection: AsyncConnection, row: dict[str, Any]
) -> str:
    sanction = (
        await connection.execute(
            text("""SELECT * FROM trust_safety.moderation_sanctions
                    WHERE case_id=:case FOR UPDATE"""), {"case": row["id"]}
        )
    ).mappings().one_or_none()
    if sanction is None:
        return "not_applicable"
    state = cast(dict[str, Any], sanction["previous_state"] or {})
    subject_type, component = row["subject_type"], row["subject_component"]
    current_version = await _current_subject_version(connection, row)
    if current_version != sanction["subject_version_after"]:
        await connection.execute(text("""UPDATE trust_safety.moderation_sanctions
          SET status='superseded',reversed_at=now() WHERE id=:id"""), {"id": sanction["id"]})
        return "newer_version_kept"
    if subject_type == "profile":
        evidence = cast(dict[str, Any], state.get("evidence") or {})
        if component == "avatar":
            asset = evidence.get("value")
            await connection.execute(text("UPDATE media.assets SET state='ready',updated_at=now() WHERE id=:asset AND state='moderation_hidden'"), {"asset": asset})
            result = await connection.execute(text("UPDATE accounts.profiles SET avatar_asset_id=:asset,version=version+1,updated_at=now() WHERE user_id=:id"), {"asset": asset, "id": row["subject_id"]})
        elif component == "background":
            asset = evidence.get("value")
            await connection.execute(text("UPDATE media.assets SET state='ready',updated_at=now() WHERE id=:asset AND state='moderation_hidden'"), {"asset": asset})
            result = await connection.execute(text("UPDATE accounts.profiles SET background_asset_id=:asset,version=version+1,updated_at=now() WHERE user_id=:id"), {"asset": asset, "id": row["subject_id"]})
        elif component == "bio":
            result = await connection.execute(text("UPDATE accounts.profiles SET bio=:value,version=version+1,updated_at=now() WHERE user_id=:id"), {"value": evidence.get("value"), "id": row["subject_id"]})
        else:
            result = await connection.execute(text("UPDATE accounts.profiles SET display_name=:value,version=version+1,updated_at=now() WHERE user_id=:id"), {"value": evidence.get("value"), "id": row["subject_id"]})
    elif subject_type == "chat_message":
        result = await connection.execute(text("UPDATE communication.messages SET hidden_at=NULL,hidden_by_case_id=NULL WHERE id=:id AND hidden_by_case_id=:case"), {"id": row["subject_id"], "case": row["id"]})
    elif subject_type == "q_and_a_answer":
        result = await connection.execute(text("UPDATE discovery.looking_post_questions SET answer_hidden_at=NULL,answer_hidden_by_case_id=NULL WHERE id=:id AND answer_hidden_by_case_id=:case"), {"id": row["subject_id"], "case": row["id"]})
    elif subject_type == "event":
        result = await connection.execute(text("""
          UPDATE events.events e SET lifecycle_status=CASE
            WHEN r.ends_at<=now() THEN 'finished' ELSE :status END,
            moderation_status=:moderation,version=version+1,updated_at=now()
          FROM events.event_revisions r
          WHERE e.id=:id AND r.id=COALESCE(e.approved_revision_id,e.current_revision_id)
            AND e.lifecycle_status='hidden' AND e.moderation_deleted_at IS NULL
        """), {"status": state.get("lifecycle_status"), "moderation": state.get("moderation_status"), "id": row["subject_id"]})
    elif subject_type == "looking_post":
        result = await connection.execute(text("UPDATE discovery.looking_posts SET status=:status,closed_at=:closed,delete_after=:delete_after,version=version+1 WHERE id=:id AND status='hidden' AND expires_at>now()"), {"status": state.get("status"), "closed": state.get("closed_at"), "delete_after": state.get("delete_after"), "id": row["subject_id"]})
    else:
        return "not_applicable"
    restored = result.rowcount == 1
    await connection.execute(text("UPDATE trust_safety.moderation_sanctions SET status=:status,reversed_at=now() WHERE id=:id"), {"status": "restored" if restored else "reversed_without_restore", "id": sanction["id"]})
    return "restored" if restored else "expired_subject"


async def decide_appeal(
    engine: AsyncEngine,
    *,
    public_id: str,
    actor_staff_id: UUID,
    decision: AppealDecision,
    staff_note: str,
    expected_version: int,
    idempotency_key: UUID,
) -> None:
    async with engine.begin() as connection:
        if await connection.scalar(
            text(
                "SELECT id FROM trust_safety.case_decisions WHERE idempotency_key=:key"
            ),
            {"key": idempotency_key},
        ):
            return
        row = (
            (
                await connection.execute(
                    text("""
                    SELECT c.*,a.id AS appeal_id,a.status AS appeal_status
                    FROM trust_safety.moderation_cases c
                    JOIN trust_safety.appeals a ON a.case_id=c.id
                    WHERE c.public_id=:public FOR UPDATE OF c,a
                    """),
                    {"public": public_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise CaseModerationError("appeal_not_found")
        if (
            row["appeal_status"] not in {"submitted", "reviewing"}
            or row["version"] != expected_version
        ):
            raise CaseModerationError("case_version_conflict")
        db_decision = f"appeal_{decision}"
        await connection.execute(
            text("""
          INSERT INTO trust_safety.case_decisions
            (id,case_id,actor_staff_id,decision_type,subject_component,staff_note,idempotency_key,case_version)
          VALUES (:id,:case,:actor,:decision,:component,:note,:key,:version)
        """),
            {
                "id": uuid4(),
                "case": row["id"],
                "actor": actor_staff_id,
                "decision": db_decision,
                "component": row["subject_component"],
                "note": staff_note,
                "key": idempotency_key,
                "version": expected_version,
            },
        )
        await connection.execute(
            text(
                "UPDATE trust_safety.appeals SET status=:status,decided_at=now() WHERE id=:id"
            ),
            {"status": decision, "id": row["appeal_id"]},
        )
        await connection.execute(
            text(
                "UPDATE trust_safety.moderation_cases SET version=version+1,updated_at=now() WHERE id=:id"
            ),
            {"id": row["id"]},
        )
        if decision == "reversed":
            restoration = await _reverse_sanction(connection, dict(row))
            await connection.execute(
                text(
                    "UPDATE trust_safety.profile_violations SET status='reversed',reversed_at=now() WHERE case_id=:case AND status IN ('pending','confirmed')"
                ),
                {"case": row["id"]},
            )
            await connection.execute(text("DELETE FROM trust_safety.profile_restrictions WHERE source_violation_id IN (SELECT id FROM trust_safety.profile_violations WHERE case_id=:case)"), {"case": row["id"]})
            label = "Решение отменено по апелляции"
            if row["subject_type"] == "event" and restoration == "restored":
                await _notify_event_audience(
                    connection,
                    event_id=row["subject_id"],
                    case_id=row["id"],
                    kind="event_moderation_restored",
                    title="Событие снова доступно",
                    body="Решение модерации отменено по апелляции.",
                    business_suffix="restored",
                )
        else:
            await _confirm_violation(connection, row["id"])
            label = "Первоначальное решение подтверждено"
        await _timeline(connection, row["id"], db_decision, label)
        await connection.execute(
            text("""
          INSERT INTO communication.notifications
            (id,recipient_user_id,kind,importance,title,body,subject_type,subject_id,
             deep_link,created_at,business_key,delivery_policy,telegram_status)
          VALUES (:id,:user,'moderation_appeal','critical','Решение по апелляции',
                  :body,'moderation_case',:case,:link,now(),:key,
                  'telegram_and_in_app','pending')
          ON CONFLICT (business_key) WHERE business_key IS NOT NULL DO NOTHING
        """),
            {
                "id": uuid4(),
                "user": row["subject_owner_user_id"],
                "case": row["id"],
                "body": label,
                "link": f"/app/cases/{public_id}",
                "key": f"case:{row['id']}:appeal:{decision}",
            },
        )
        await _audit(
            connection, actor_staff_id, "case.appeal_decision", public_id, decision
        )


async def _confirm_violation(connection: AsyncConnection, case_id: UUID) -> bool:
    violation = (
        (
            await connection.execute(
                text("""
              UPDATE trust_safety.profile_violations SET status='confirmed',confirmed_at=now()
              WHERE case_id=:case AND status='pending' RETURNING id,user_id,direction
            """),
                {"case": case_id},
            )
        )
        .mappings()
        .one_or_none()
    )
    if violation is None:
        return False
    count = int(
        await connection.scalar(
            text("""
      SELECT count(*) FROM trust_safety.profile_violations
      WHERE user_id=:user AND direction=:direction AND status='confirmed'
        AND created_at>=now()-interval '180 days'
    """),
            {"user": violation["user_id"], "direction": violation["direction"]},
        )
        or 0
    )
    if count >= 2:
        days = 30 if count == 2 else 90
        ends_at = datetime.now(UTC) + timedelta(days=days)
        await connection.execute(
            text("""
          INSERT INTO trust_safety.profile_restrictions
            (id,user_id,direction,source_violation_id,starts_at,ends_at)
          VALUES (:id,:user,:direction,:violation,now(),:ends_at)
          ON CONFLICT (source_violation_id) DO NOTHING
        """),
            {
                "id": uuid4(),
                "user": violation["user_id"],
                "direction": violation["direction"],
                "violation": violation["id"],
                "ends_at": ends_at,
            },
        )
        case_public_id = await connection.scalar(
            text("SELECT public_id FROM trust_safety.moderation_cases WHERE id=:id"),
            {"id": case_id},
        )
        await connection.execute(
            text("""
          INSERT INTO communication.notifications
            (id,recipient_user_id,kind,importance,title,body,subject_type,subject_id,
             deep_link,created_at,expires_at,business_key,delivery_policy,telegram_status)
          VALUES (:id,:user,'profile_restriction','critical','Ограничение профиля',
                  :body,'moderation_case',:case,:link,now(),:ends_at,:key,
                  'telegram_and_in_app','pending')
          ON CONFLICT (business_key) WHERE business_key IS NOT NULL DO NOTHING
        """),
            {
                "id": uuid4(),
                "user": violation["user_id"],
                "case": case_id,
                "body": f"Редактирование раздела профиля ограничено до {ends_at:%d.%m.%Y}. Остальные функции приложения доступны.",
                "link": f"/app/cases/{case_public_id}",
                "ends_at": ends_at,
                "key": f"case:{case_id}:restriction",
            },
        )
    return True


async def confirm_due_violations(engine: AsyncEngine) -> int:
    async with engine.begin() as connection:
        ids = list(
            (
                await connection.scalars(
                    text("""
          SELECT case_id FROM trust_safety.profile_violations v
          WHERE v.status='pending' AND v.confirm_after<=now()
            AND NOT EXISTS (SELECT 1 FROM trust_safety.appeals a
                            WHERE a.case_id=v.case_id AND a.status IN ('submitted','reviewing'))
          FOR UPDATE SKIP LOCKED
        """)
                )
            ).all()
        )
        confirmed = 0
        for case_id in ids:
            confirmed += int(await _confirm_violation(connection, case_id))
        return confirmed


async def finalize_due_event_moderation(engine: AsyncEngine) -> int:
    """Irreversibly redact hidden events once appeal recovery is no longer possible."""
    async with engine.begin() as connection:
        rows = (
            await connection.execute(text("""
              SELECT c.id AS case_id,c.subject_id AS event_id
              FROM trust_safety.moderation_cases c
              JOIN trust_safety.moderation_sanctions s ON s.case_id=c.id
              WHERE c.subject_type='event' AND s.status='active'
                AND c.appeal_deadline IS NOT NULL
                AND (c.appeal_deadline<=now() OR EXISTS (
                  SELECT 1 FROM trust_safety.appeals a
                  WHERE a.case_id=c.id AND a.status='upheld'))
                AND NOT EXISTS (
                  SELECT 1 FROM trust_safety.appeals a
                  WHERE a.case_id=c.id AND a.status IN ('submitted','reviewing'))
              FOR UPDATE OF c,s SKIP LOCKED
            """))
        ).mappings().all()
        finalized = 0
        for row in rows:
            event_id, case_id = row["event_id"], row["case_id"]
            updated = await connection.execute(text("""
              UPDATE events.events SET moderation_deleted_at=now(),
                lifecycle_status='hidden',moderation_status='held',chat_enabled=false,
                capacity=NULL,version=version+1,updated_at=now()
              WHERE id=:event AND moderation_deleted_at IS NULL
            """), {"event": event_id})
            if updated.rowcount != 1:
                continue
            await _notify_event_audience(
                connection,event_id=event_id,case_id=case_id,
                kind="event_moderation_removed",title="Событие удалено",
                body="Событие окончательно удалено после завершения апелляции.",
                business_suffix="removed",
            )
            await connection.execute(text("""
              UPDATE media.assets SET state='deleted',updated_at=now()
              WHERE id IN (SELECT media_asset_id FROM events.event_photos WHERE event_id=:event)
            """), {"event": event_id})
            await connection.execute(text("DELETE FROM events.event_photos WHERE event_id=:event"), {"event": event_id})
            await connection.execute(text("DELETE FROM communication.messages WHERE event_id=:event"), {"event": event_id})
            await connection.execute(text("""
              UPDATE events.participation_episodes SET status='cancelled',closed_at=now(),
                close_reason='moderation_removed'
              WHERE event_id=:event AND status='active'
            """), {"event": event_id})
            await connection.execute(text("""
              UPDATE events.waitlist_entries SET status='cancelled',closed_at=now()
              WHERE event_id=:event AND status='waiting'
            """), {"event": event_id})
            await connection.execute(text("""
              UPDATE events.event_revisions SET title='Удалённое событие',
                description='Удалено модерацией',rules=NULL,landmark=NULL,
                location=ST_SetSRID(ST_MakePoint(0,0),4326)::geography,
                normalized_address='Удалено',organizer_address=NULL,
                organizer_street=NULL,organizer_place=NULL,street_name='Удалено'
              WHERE event_id=:event
            """), {"event": event_id})
            await connection.execute(text("""
              UPDATE trust_safety.moderation_sanctions SET status='finalized'
              WHERE case_id=:case AND status='active'
            """), {"case": case_id})
            await _timeline(connection, case_id, "event_removed", "Событие окончательно удалено")
            finalized += 1
        return finalized


async def purge_expired_evidence(engine: AsyncEngine, media_root: Path) -> int:
    """Remove private snapshots after the appeal/audit retention window."""
    paths: set[Path] = set()
    async with engine.begin() as connection:
        rows = (
            (
                await connection.execute(
                    text("""
                  SELECT r.id,r.evidence_snapshot
                  FROM trust_safety.reports r
                  JOIN trust_safety.moderation_cases c ON c.id=r.case_id
                  WHERE r.evidence_snapshot IS NOT NULL AND c.resolved_at<now()-interval '30 days'
                    AND NOT EXISTS (SELECT 1 FROM trust_safety.appeals a
                                    WHERE a.case_id=c.id AND a.status IN ('submitted','reviewing'))
                  FOR UPDATE OF r SKIP LOCKED
                """)
                )
            )
            .mappings()
            .all()
        )
        for row in rows:
            snapshot = cast(dict[str, Any], row["evidence_snapshot"] or {})
            if snapshot.get("component") in {"avatar", "background", "photo"} and snapshot.get(
                "value"
            ):
                try:
                    asset_id = UUID(str(snapshot["value"]))
                except ValueError:
                    asset_id = None
                if asset_id:
                    await connection.execute(
                        text("UPDATE media.assets SET state='deleted',updated_at=now() "
                             "WHERE id=:id AND state='moderation_hidden'"),
                        {"id": asset_id},
                    )
                    keys = list(
                        (
                            await connection.scalars(
                                text("""
                      SELECT storage_key FROM media.asset_variants WHERE source_asset_id=:id
                      UNION SELECT storage_key FROM media.assets WHERE id=:id
                    """),
                                {"id": asset_id},
                            )
                        ).all()
                    )
                    paths.update(media_root / key for key in keys)
            await connection.execute(
                text(
                    "UPDATE trust_safety.reports SET evidence_snapshot=NULL WHERE id=:id"
                ),
                {"id": row["id"]},
            )
    for path in paths:
        path.unlink(missing_ok=True)
    return len(rows)


async def active_profile_restriction(
    connection: AsyncConnection, user_id: UUID, direction: str
) -> datetime | None:
    return await connection.scalar(
        text("""
      SELECT max(ends_at) FROM trust_safety.profile_restrictions
      WHERE user_id=:user AND direction=:direction AND ends_at>now()
    """),
        {"user": user_id, "direction": direction},
    )


async def _timeline(
    connection: AsyncConnection, case_id: UUID, event: str, label: str
) -> None:
    await connection.execute(
        text("""
      INSERT INTO trust_safety.case_timeline_entries(id,case_id,event_type,public_label)
      VALUES (:id,:case,:event,:label)
    """),
        {"id": uuid4(), "case": case_id, "event": event, "label": label},
    )


async def _notify_owner(
    connection: AsyncConnection,
    case: dict[str, Any],
    component: str | None,
    decision: Decision,
    public_id: str,
    deadline: datetime | None,
) -> None:
    owner = case.get("subject_owner_user_id")
    if owner is None:
        return
    labels = {
        ("profile", "avatar"): "Аватар профиля",
        ("profile", "background"): "Фон профиля",
        ("profile", "display_name"): "Имя профиля",
        ("profile", "bio"): "Описание профиля",
        ("event", "photo"): "Фотография события",
        ("event", "title"): "Название события",
        ("looking_post", "title"): "Название идеи",
        ("chat_message", "message"): "Сообщение",
        ("q_and_a_answer", "answer"): "Ответ в Q&A",
    }
    component_label = labels.get((case["subject_type"], component), "Контент")
    title = (
        f"{component_label} снято до исправления"
        if decision == "hold_for_correction"
        else f"{component_label} скрыт"
    )
    deadline_label = deadline.strftime("%d.%m.%Y, %H:%M") if deadline else ""
    body = f"Решение по обращению {public_id}. Апелляцию можно подать до {deadline_label}."
    await connection.execute(
        text("""
      INSERT INTO communication.notifications
        (id,recipient_user_id,kind,importance,title,body,subject_type,subject_id,
         deep_link,created_at,expires_at,business_key,delivery_policy,telegram_status)
      VALUES (:id,:user,'moderation_action','critical',:title,:body,
              'moderation_case',:case_id,:link,now(),:expires,:key,
              'telegram_and_in_app','pending')
      ON CONFLICT (business_key) WHERE business_key IS NOT NULL DO NOTHING
    """),
        {
            "id": uuid4(),
            "user": owner,
            "body": body,
            "title": title,
            "case_id": case["id"],
            "link": f"/app/cases/{public_id}",
            "expires": deadline,
            "key": f"case:{case['id']}:decision",
        },
    )


async def _notify_event_audience(
    connection: AsyncConnection,
    *,
    event_id: UUID,
    case_id: UUID,
    kind: str,
    title: str,
    body: str,
    business_suffix: str,
) -> None:
    await connection.execute(text("""
      INSERT INTO communication.notifications
        (id,recipient_user_id,kind,importance,title,body,subject_type,subject_id,
         deep_link,created_at,business_key,delivery_policy,telegram_status)
      SELECT gen_random_uuid(),audience.user_id,:kind,'critical',:title,:body,
             'moderation_case',:case,
             CASE WHEN audience.user_id=event.creator_user_id
                  THEN '/app/cases/' || c.public_id ELSE NULL END,now(),
             'case:' || CAST(:case AS text) || ':audience:' || :suffix || ':' || CAST(audience.user_id AS text),
             'telegram_and_in_app','pending'
      FROM trust_safety.moderation_cases c
      JOIN events.events event ON event.id=:event
      CROSS JOIN LATERAL (
        SELECT e.creator_user_id AS user_id FROM events.events e WHERE e.id=:event
        UNION SELECT p.user_id FROM events.participation_episodes p
          WHERE p.event_id=:event AND p.status='active'
        UNION SELECT w.user_id FROM events.waitlist_entries w
          WHERE w.event_id=:event AND w.status='waiting'
      ) audience
      WHERE c.id=:case AND audience.user_id IS NOT NULL
      ON CONFLICT (business_key) WHERE business_key IS NOT NULL DO NOTHING
    """), {"event": event_id,"case": case_id,"kind": kind,"title": title,
             "body": body,"suffix": business_suffix})


async def _audit(
    connection: AsyncConnection, actor: UUID, action: str, public_id: str, result: str
) -> None:
    details = json.dumps({"case_public_id": public_id, "decision": result})
    await connection.execute(
        text("""
      INSERT INTO trust_safety.staff_audit_log
        (id,actor_staff_id,action,result,details)
      VALUES (:id,:actor,:action,'success',CAST(:details AS jsonb))
    """),
        {
            "id": uuid4(),
            "actor": actor,
            "action": action,
            "details": details,
        },
    )
