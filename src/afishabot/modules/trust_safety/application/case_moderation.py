"""Staff moderation queues, immutable decisions and profile sanctions."""
# ruff: noqa: E501

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal, cast
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

QueueName = Literal["reports", "appeals"]
Decision = Literal["dismiss", "hide_content"]
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
    if queue == "appeals":
        statement = """
          SELECT c.public_id,c.subject_type,c.subject_component,c.priority,c.version,
                 c.created_at,c.updated_at,r.reason_code,a.created_at AS appeal_created_at,
                 a.status AS appeal_status
          FROM trust_safety.appeals a
          JOIN trust_safety.moderation_cases c ON c.id=a.case_id
          LEFT JOIN LATERAL (
            SELECT reason_code FROM trust_safety.reports
            WHERE case_id=c.id ORDER BY created_at LIMIT 1
          ) r ON true
          WHERE a.status IN ('submitted','reviewing')
            AND (:before IS NULL OR a.created_at<:before)
          ORDER BY a.created_at,c.id LIMIT :limit
        """
    else:
        statement = """
          SELECT c.public_id,c.subject_type,c.subject_component,c.priority,c.version,
                 c.created_at,c.updated_at,r.reason_code,NULL::timestamptz AS appeal_created_at,
                 NULL::varchar AS appeal_status
          FROM trust_safety.moderation_cases c
          LEFT JOIN LATERAL (
            SELECT reason_code FROM trust_safety.reports
            WHERE case_id=c.id ORDER BY created_at LIMIT 1
          ) r ON true
          WHERE c.status<>'resolved' AND (:before IS NULL OR c.created_at<:before)
          ORDER BY CASE c.priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 ELSE 2 END,
                   c.created_at,c.id LIMIT :limit
        """
    async with engine.connect() as connection:
        rows = (
            (
                await connection.execute(
                    text(statement), {"before": before, "limit": limit}
                )
            )
            .mappings()
            .all()
        )
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
    result["timeline"] = [dict(row) for row in timeline]
    result["decisions"] = [dict(row) for row in decisions]
    result["appeal"] = dict(appeal) if appeal else None
    result["previous_violations"] = previous
    return result


async def _subject_projection(
    connection: AsyncConnection, case: dict[str, Any]
) -> dict[str, Any] | None:
    subject_type, subject_id = case["subject_type"], case["subject_id"]
    statements = {
        "event": "SELECT title,lifecycle_status AS status FROM events.events WHERE id=:id",
        "looking_post": "SELECT title,status FROM discovery.looking_posts WHERE id=:id",
        "q_and_a_answer": "SELECT answer,answer_hidden_at IS NOT NULL AS hidden FROM discovery.looking_post_questions WHERE id=:id",
        "profile": "SELECT public_id,display_name,bio,avatar_asset_id IS NOT NULL AS has_avatar,background_asset_id IS NOT NULL AS has_background FROM accounts.profiles WHERE user_id=:id",
    }
    statement = statements.get(subject_type)
    if statement is None:
        return {"type": subject_type, "available": False}
    row = (
        (await connection.execute(text(statement), {"id": subject_id}))
        .mappings()
        .one_or_none()
    )
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
            text("SELECT id FROM trust_safety.case_decisions WHERE idempotency_key=:key"),
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
        if decision == "hide_content":
            await _hide_subject(connection, dict(case), chosen)
        now = datetime.now(UTC)
        appeal_deadline = now + timedelta(days=3) if decision == "hide_content" else None
        await connection.execute(
            text("""
            INSERT INTO trust_safety.case_decisions
              (id,case_id,actor_staff_id,decision_type,subject_component,staff_note,
               idempotency_key,case_version)
            VALUES (:id,:case,:actor,:decision,:component,:note,:key,:version)
            """),
            {"id": uuid4(), "case": case["id"], "actor": actor_staff_id,
             "decision": decision, "component": chosen, "note": staff_note,
             "key": idempotency_key, "version": expected_version},
        )
        await connection.execute(
            text("""
            UPDATE trust_safety.moderation_cases SET status='resolved',resolved_at=:now,
              appeal_deadline=:deadline,subject_component=COALESCE(:component,subject_component),
              version=version+1,updated_at=:now WHERE id=:id
            """),
            {"now": now, "deadline": appeal_deadline, "component": chosen, "id": case["id"]},
        )
        await connection.execute(
            text("""
            UPDATE trust_safety.profile_reports
            SET status=:status,decided_at=:now
            WHERE id=:id AND status IN ('pending','reviewed')
            """),
            {
                "status": "actioned" if decision == "hide_content" else "dismissed",
                "now": now,
                "id": case["id"],
            },
        )
        label = "Нарушение подтверждено" if decision == "hide_content" else "Жалоба отклонена"
        await _timeline(connection, case["id"], "resolved", label)
        direction = _direction(chosen) if case["subject_type"] == "profile" else None
        if decision == "hide_content" and direction:
            await connection.execute(
                text("""
                INSERT INTO trust_safety.profile_violations
                  (id,case_id,user_id,direction,confirm_after)
                VALUES (:id,:case,:user,:direction,:after)
                """),
                {"id": uuid4(), "case": case["id"], "user": case["subject_owner_user_id"],
                 "direction": direction, "after": appeal_deadline},
            )
        if decision == "hide_content":
            await _notify_owner(connection, dict(case), chosen, public_id, appeal_deadline)
        await _audit(connection, actor_staff_id, "case.decision", public_id, decision)


async def _hide_subject(
    connection: AsyncConnection, case: dict[str, Any], component: str | None
) -> None:
    subject_type = case["subject_type"]
    if subject_type == "event":
        await connection.execute(text("UPDATE events.events SET lifecycle_status='hidden',updated_at=now() WHERE id=:id"), {"id": case["subject_id"]})
    elif subject_type == "looking_post":
        await connection.execute(text("UPDATE discovery.looking_posts SET status='hidden',updated_at=now() WHERE id=:id"), {"id": case["subject_id"]})
    elif subject_type == "q_and_a_answer":
        await connection.execute(text("UPDATE discovery.looking_post_questions SET answer_hidden_at=now() WHERE id=:id"), {"id": case["subject_id"]})
    elif subject_type == "profile":
        if component not in {"avatar", "background", "bio", "display_name"}:
            raise CaseModerationError("profile_component_required")
        if component == "avatar":
            await connection.execute(text("UPDATE media.assets SET state='deleted',updated_at=now() WHERE id=(SELECT avatar_asset_id FROM accounts.profiles WHERE user_id=:id)"), {"id": case["subject_id"]})
            statement = "UPDATE accounts.profiles SET avatar_asset_id=NULL,version=version+1,updated_at=now() WHERE user_id=:id"
        elif component == "background":
            await connection.execute(text("UPDATE media.assets SET state='deleted',updated_at=now() WHERE id=(SELECT background_asset_id FROM accounts.profiles WHERE user_id=:id)"), {"id": case["subject_id"]})
            statement = "UPDATE accounts.profiles SET background_asset_id=NULL,version=version+1,updated_at=now() WHERE user_id=:id"
        elif component == "bio":
            statement = "UPDATE accounts.profiles SET bio=NULL,version=version+1,updated_at=now() WHERE user_id=:id"
        else:
            statement = "UPDATE accounts.profiles SET display_name='Пользователь',display_name_changed_at=NULL,version=version+1,updated_at=now() WHERE user_id=:id"
        await connection.execute(text(statement), {"id": case["subject_id"]})
    else:
        raise CaseModerationError("subject_action_not_supported")


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
        if await connection.scalar(text("SELECT id FROM trust_safety.case_decisions WHERE idempotency_key=:key"), {"key": idempotency_key}):
            return
        row = (
            (
                await connection.execute(
                    text("""
                    SELECT c.*,a.id AS appeal_id,a.status AS appeal_status
                    FROM trust_safety.moderation_cases c
                    JOIN trust_safety.appeals a ON a.case_id=c.id
                    WHERE c.public_id=:public FOR UPDATE OF c,a
                    """), {"public": public_id}
                )
            ).mappings().one_or_none()
        )
        if row is None:
            raise CaseModerationError("appeal_not_found")
        if row["appeal_status"] not in {"submitted", "reviewing"} or row["version"] != expected_version:
            raise CaseModerationError("case_version_conflict")
        db_decision = f"appeal_{decision}"
        await connection.execute(text("""
          INSERT INTO trust_safety.case_decisions
            (id,case_id,actor_staff_id,decision_type,subject_component,staff_note,idempotency_key,case_version)
          VALUES (:id,:case,:actor,:decision,:component,:note,:key,:version)
        """), {"id":uuid4(),"case":row["id"],"actor":actor_staff_id,"decision":db_decision,
                 "component":row["subject_component"],"note":staff_note,"key":idempotency_key,"version":expected_version})
        await connection.execute(text("UPDATE trust_safety.appeals SET status=:status,decided_at=now() WHERE id=:id"), {"status":decision,"id":row["appeal_id"]})
        await connection.execute(text("UPDATE trust_safety.moderation_cases SET version=version+1,updated_at=now() WHERE id=:id"), {"id":row["id"]})
        if decision == "reversed":
            await connection.execute(text("UPDATE trust_safety.profile_violations SET status='reversed',reversed_at=now() WHERE case_id=:case AND status='pending'"), {"case":row["id"]})
            label = "Решение отменено по апелляции"
        else:
            await _confirm_violation(connection, row["id"])
            label = "Первоначальное решение подтверждено"
        await _timeline(connection, row["id"], db_decision, label)
        await connection.execute(text("""
          INSERT INTO communication.notifications
            (id,recipient_user_id,kind,importance,title,body,subject_type,subject_id,
             deep_link,created_at,business_key,delivery_policy,telegram_status)
          VALUES (:id,:user,'moderation_appeal','critical','Решение по апелляции',
                  :body,'moderation_case',:case,:link,now(),:key,
                  'telegram_and_in_app','pending')
          ON CONFLICT (business_key) WHERE business_key IS NOT NULL DO NOTHING
        """), {
            "id": uuid4(), "user": row["subject_owner_user_id"], "case": row["id"],
            "body": label, "link": f"/app/cases/{public_id}",
            "key": f"case:{row['id']}:appeal:{decision}",
        })
        await _audit(connection, actor_staff_id, "case.appeal_decision", public_id, decision)


async def _confirm_violation(connection: AsyncConnection, case_id: UUID) -> bool:
    violation = (
        (
            await connection.execute(text("""
              UPDATE trust_safety.profile_violations SET status='confirmed',confirmed_at=now()
              WHERE case_id=:case AND status='pending' RETURNING id,user_id,direction
            """), {"case":case_id})
        ).mappings().one_or_none()
    )
    if violation is None:
        return False
    count = int(await connection.scalar(text("""
      SELECT count(*) FROM trust_safety.profile_violations
      WHERE user_id=:user AND direction=:direction AND status='confirmed'
        AND created_at>=now()-interval '180 days'
    """), {"user":violation["user_id"],"direction":violation["direction"]}) or 0)
    if count >= 2:
        days = 30 if count == 2 else 90
        ends_at = datetime.now(UTC) + timedelta(days=days)
        await connection.execute(text("""
          INSERT INTO trust_safety.profile_restrictions
            (id,user_id,direction,source_violation_id,starts_at,ends_at)
          VALUES (:id,:user,:direction,:violation,now(),:ends_at)
          ON CONFLICT (source_violation_id) DO NOTHING
        """), {"id":uuid4(),"user":violation["user_id"],"direction":violation["direction"],
                 "violation":violation["id"],"ends_at":ends_at})
        case_public_id = await connection.scalar(
            text("SELECT public_id FROM trust_safety.moderation_cases WHERE id=:id"),
            {"id": case_id},
        )
        await connection.execute(text("""
          INSERT INTO communication.notifications
            (id,recipient_user_id,kind,importance,title,body,subject_type,subject_id,
             deep_link,created_at,expires_at,business_key,delivery_policy,telegram_status)
          VALUES (:id,:user,'profile_restriction','critical','Ограничение профиля',
                  :body,'moderation_case',:case,:link,now(),:ends_at,:key,
                  'telegram_and_in_app','pending')
          ON CONFLICT (business_key) WHERE business_key IS NOT NULL DO NOTHING
        """), {
            "id": uuid4(), "user": violation["user_id"], "case": case_id,
            "body": f"Редактирование раздела профиля ограничено до {ends_at:%d.%m.%Y}. Остальные функции приложения доступны.",
            "link": f"/app/cases/{case_public_id}", "ends_at": ends_at,
            "key": f"case:{case_id}:restriction",
        })
    return True


async def confirm_due_violations(engine: AsyncEngine) -> int:
    async with engine.begin() as connection:
        ids = list((await connection.scalars(text("""
          SELECT case_id FROM trust_safety.profile_violations v
          WHERE v.status='pending' AND v.confirm_after<=now()
            AND NOT EXISTS (SELECT 1 FROM trust_safety.appeals a
                            WHERE a.case_id=v.case_id AND a.status IN ('submitted','reviewing'))
          FOR UPDATE SKIP LOCKED
        """))).all())
        confirmed = 0
        for case_id in ids:
            confirmed += int(await _confirm_violation(connection, case_id))
        return confirmed


async def purge_expired_evidence(engine: AsyncEngine, media_root: Path) -> int:
    """Remove private snapshots after the appeal/audit retention window."""
    paths: set[Path] = set()
    async with engine.begin() as connection:
        rows = (
            (
                await connection.execute(text("""
                  SELECT r.id,r.evidence_snapshot
                  FROM trust_safety.reports r
                  JOIN trust_safety.moderation_cases c ON c.id=r.case_id
                  WHERE r.evidence_snapshot IS NOT NULL AND c.resolved_at<now()-interval '30 days'
                    AND NOT EXISTS (SELECT 1 FROM trust_safety.appeals a
                                    WHERE a.case_id=c.id AND a.status IN ('submitted','reviewing'))
                  FOR UPDATE OF r SKIP LOCKED
                """))
            ).mappings().all()
        )
        for row in rows:
            snapshot = cast(dict[str, Any], row["evidence_snapshot"] or {})
            if snapshot.get("component") in {"avatar", "background"} and snapshot.get("value"):
                try:
                    asset_id = UUID(str(snapshot["value"]))
                except ValueError:
                    asset_id = None
                if asset_id:
                    keys = list((await connection.scalars(text("""
                      SELECT storage_key FROM media.asset_variants WHERE source_asset_id=:id
                      UNION SELECT storage_key FROM media.assets WHERE id=:id
                    """), {"id": asset_id})).all())
                    paths.update(media_root / key for key in keys)
            await connection.execute(
                text("UPDATE trust_safety.reports SET evidence_snapshot=NULL WHERE id=:id"),
                {"id": row["id"]},
            )
    for path in paths:
        path.unlink(missing_ok=True)
    return len(rows)


async def active_profile_restriction(
    connection: AsyncConnection, user_id: UUID, direction: str
) -> datetime | None:
    return await connection.scalar(text("""
      SELECT max(ends_at) FROM trust_safety.profile_restrictions
      WHERE user_id=:user AND direction=:direction AND ends_at>now()
    """), {"user":user_id,"direction":direction})


async def _timeline(connection: AsyncConnection, case_id: UUID, event: str, label: str) -> None:
    await connection.execute(text("""
      INSERT INTO trust_safety.case_timeline_entries(id,case_id,event_type,public_label)
      VALUES (:id,:case,:event,:label)
    """), {"id":uuid4(),"case":case_id,"event":event,"label":label})


async def _notify_owner(
    connection: AsyncConnection, case: dict[str, Any], component: str | None,
    public_id: str, deadline: datetime | None,
) -> None:
    owner = case.get("subject_owner_user_id")
    if owner is None:
        return
    labels: dict[str | None, str] = {
        "avatar": "Аватар", "background": "Фон профиля",
        "bio": "Описание профиля", "display_name": "Имя профиля",
        None: "Контент",
    }
    component_label = labels.get(component, "Контент")
    body = f"{component_label} скрыт после проверки. Апелляцию можно подать в течение 3 дней. Повторное нарушение может ограничить редактирование профиля."
    await connection.execute(text("""
      INSERT INTO communication.notifications
        (id,recipient_user_id,kind,importance,title,body,subject_type,subject_id,
         deep_link,created_at,expires_at,business_key,delivery_policy,telegram_status)
      VALUES (:id,:user,'profile_moderation','critical','Изменение профиля',:body,
              'moderation_case',:case_id,:link,now(),:expires,:key,
              'telegram_and_in_app','pending')
      ON CONFLICT (business_key) WHERE business_key IS NOT NULL DO NOTHING
    """), {"id":uuid4(),"user":owner,"body":body,"case_id":case["id"],
             "link":f"/app/cases/{public_id}","expires":deadline,
             "key":f"case:{case['id']}:decision"})


async def _audit(
    connection: AsyncConnection, actor: UUID, action: str, public_id: str, result: str
) -> None:
    await connection.execute(text("""
      INSERT INTO trust_safety.staff_audit_log
        (id,actor_staff_id,action,result,details)
      VALUES (:id,:actor,:action,'success',jsonb_build_object('case_public_id',:public,'decision',:decision))
    """), {"id":uuid4(),"actor":actor,"action":action,"public":public_id,"decision":result})
