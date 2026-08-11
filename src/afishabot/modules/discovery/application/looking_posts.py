"""LookingPost feed and Q&A use cases.

The module exposes only safe projections; question ownership is checked before
the private asker identity is ever selected.
"""

from datetime import UTC, datetime
from hashlib import sha256
from typing import Any, Literal
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine


Sort = Literal["new", "old", "popular"]
FeedCursor = tuple[int | None, datetime, UUID]


class LookingPostError(Exception):
    pass


class LookingPostNotFound(LookingPostError):
    pass


class LookingPostConflict(LookingPostError):
    pass


class LookingPostClosed(LookingPostConflict):
    pass


def _compact(value: str, maximum: int) -> str:
    result = " ".join(value.split())
    if not result or len(result) > maximum or any(ord(char) < 32 for char in result):
        raise LookingPostError("invalid_text")
    return result


async def create_looking_post(
    engine: AsyncEngine, *, user_id: UUID, city_id: UUID, category_id: UUID,
    title: str, body: str, idempotency_key: UUID,
) -> dict[str, Any]:
    title = _compact(title, 30); body = _compact(body, 300)
    fingerprint = _fingerprint("create", city_id, category_id, title, body)
    post_id = uuid4()
    async with engine.begin() as connection:
        previous = await _existing_request(connection, user_id, idempotency_key, fingerprint)
        if previous is not None:
            post_id = previous
        else:
            city = await connection.scalar(text("SELECT 1 FROM discovery.cities WHERE id=:id AND is_active AND looking_posts_enabled"), {"id": city_id})
            category = await connection.scalar(text("SELECT 1 FROM discovery.categories WHERE id=:id AND is_active AND organizer_selectable AND NOT is_special"), {"id": category_id})
            if city is None: raise LookingPostError("city_not_available")
            if category is None: raise LookingPostError("category_not_available")
            await connection.execute(text("""
                INSERT INTO discovery.looking_posts (id,author_user_id,city_id,category_id,title,body)
                VALUES (:id,:user,:city,:category,:title,:body)
            """), {"id": post_id, "user": user_id, "city": city_id, "category": category_id, "title": title, "body": body})
            await _remember_request(connection, user_id, idempotency_key, "create", fingerprint, post_id)
    return await looking_post_detail(engine, post_id=post_id, viewer_id=user_id)


async def looking_post_feed(
    engine: AsyncEngine, *, city_id: UUID, viewer_id: UUID | None, sort: Sort,
    cursor: FeedCursor | None, limit: int,
) -> tuple[list[dict[str, Any]], FeedCursor | None]:
    if sort == "popular":
        order = "like_count DESC, created_at DESC, id DESC"
        cursor_sql = "AND (like_count, created_at, id) < (:likes, :at, :id)" if cursor else ""
    elif sort == "old":
        order = "created_at ASC, id ASC"; cursor_sql = "AND (created_at,id) > (:at,:id)" if cursor else ""
    else:
        order = "created_at DESC, id DESC"; cursor_sql = "AND (created_at,id) < (:at,:id)" if cursor else ""
    params: dict[str, Any] = {"city": city_id, "viewer": viewer_id, "limit": limit + 1}
    if cursor:
        params.update(at=cursor[1], id=cursor[2], likes=cursor[0])
    async with engine.connect() as connection:
        rows = (await connection.execute(text(f"""
            WITH feed AS (
              SELECT p.id,p.author_user_id,p.title,p.body,p.status,p.created_at,p.expires_at,
                   c.name AS city,cat.name AS category,pr.public_id,pr.display_name,pr.avatar_asset_id,
                   COALESCE((SELECT count(*) FROM discovery.looking_post_likes l
                      WHERE l.looking_post_id=p.id AND l.active AND l.user_id<>p.author_user_id), 0) AS like_count,
                   COALESCE((SELECT count(*) FROM discovery.looking_post_questions q
                      WHERE q.looking_post_id=p.id AND q.answer IS NOT NULL), 0) AS question_count,
                   EXISTS(SELECT 1 FROM discovery.looking_post_likes l
                      WHERE l.looking_post_id=p.id AND l.user_id=:viewer AND l.active) AS viewer_liked
            FROM discovery.looking_posts p
            JOIN discovery.cities c ON c.id=p.city_id
            JOIN discovery.categories cat ON cat.id=p.category_id
            JOIN accounts.profiles pr ON pr.user_id=p.author_user_id
            WHERE p.city_id=:city AND p.status='active' AND p.expires_at>now()
            )
            SELECT * FROM feed WHERE true {cursor_sql}
            ORDER BY {order} LIMIT :limit
        """), params)).mappings().all()
    items = [_feed_item(row, viewer_id) for row in rows[:limit]]
    last = rows[limit - 1] if len(rows) > limit else None
    return items, ((int(last["like_count"]) if sort == "popular" else None, last["created_at"], last["id"]) if last else None)


def _feed_item(row: Any, viewer_id: UUID | None) -> dict[str, Any]:
    author = row["author_user_id"] == viewer_id
    effective_status = "expired" if row["status"] == "active" and row["expires_at"] <= datetime.now(UTC) else row["status"]
    remaining = max(0, int((row["expires_at"] - datetime.now(UTC)).total_seconds()))
    return {"id": row["id"], "title": row["title"], "body": row["body"], "status": effective_status, "display_status": effective_status, "remaining_seconds": remaining if effective_status == "active" else 0, "created_at": row["created_at"], "expires_at": row["expires_at"], "city": row["city"], "category": row["category"], "like_count": int(row["like_count"] or 0), "question_count": int(row["question_count"] or 0), "viewer_liked": bool(row["viewer_liked"]) if viewer_id else False, "is_author": author, "author": {"public_id": row["public_id"], "display_name": row["display_name"], "avatar_url": f"/api/profiles/{row['public_id']}/avatar?size=64" if row["avatar_asset_id"] else None, "avatar_thumbnail_url": f"/api/profiles/{row['public_id']}/avatar?size=64" if row["avatar_asset_id"] else None}}


async def looking_post_detail(engine: AsyncEngine, *, post_id: UUID, viewer_id: UUID | None) -> dict[str, Any]:
    async with engine.connect() as connection:
        row = (await connection.execute(text("""
            SELECT p.id,p.author_user_id,p.title,p.body,p.status,p.created_at,p.expires_at,
              c.name AS city,cat.name AS category,pr.public_id,pr.display_name,pr.avatar_asset_id,
              COALESCE((SELECT count(*) FROM discovery.looking_post_likes l
                WHERE l.looking_post_id=p.id AND l.active AND l.user_id<>p.author_user_id), 0) AS like_count,
              COALESCE((SELECT count(*) FROM discovery.looking_post_questions q
                WHERE q.looking_post_id=p.id AND q.answer IS NOT NULL), 0) AS question_count,
              EXISTS(SELECT 1 FROM discovery.looking_post_likes l
                WHERE l.looking_post_id=p.id AND l.user_id=:viewer AND l.active) AS viewer_liked
            FROM discovery.looking_posts p JOIN discovery.cities c ON c.id=p.city_id
              JOIN discovery.categories cat ON cat.id=p.category_id JOIN accounts.profiles pr ON pr.user_id=p.author_user_id
            WHERE p.id=:id
        """), {"id": post_id, "viewer": viewer_id})).mappings().one_or_none()
    if row is None: raise LookingPostNotFound
    if row["status"] == "hidden" and row["author_user_id"] != viewer_id:
        raise LookingPostNotFound
    return _feed_item(row, viewer_id)


async def set_looking_post_like(engine: AsyncEngine, *, post_id: UUID, user_id: UUID, active: bool) -> dict[str, Any]:
    async with engine.begin() as connection:
        post = (await connection.execute(text("SELECT author_user_id FROM discovery.looking_posts WHERE id=:id AND status='active' AND expires_at>now() FOR UPDATE"), {"id": post_id})).mappings().one_or_none()
        if post is None:
            exists = await connection.scalar(text("SELECT 1 FROM discovery.looking_posts WHERE id=:id"), {"id": post_id})
            if exists: raise LookingPostClosed("idea_closed")
            raise LookingPostNotFound
        if post["author_user_id"] == user_id: raise LookingPostError("author_cannot_like")
        await connection.execute(text("""
            INSERT INTO discovery.looking_post_likes (looking_post_id,user_id,active) VALUES (:post,:user,:active)
            ON CONFLICT (looking_post_id,user_id) DO UPDATE SET active=EXCLUDED.active,updated_at=now()
        """), {"post": post_id, "user": user_id, "active": active})
        count = await connection.scalar(text("SELECT count(*) FROM discovery.looking_post_likes WHERE looking_post_id=:post AND active"), {"post": post_id})
    return {"liked": active, "like_count": int(count or 0)}


async def questions_for_viewer(
    engine: AsyncEngine, *, post_id: UUID, viewer_id: UUID
) -> dict[str, Any]:
    async with engine.connect() as connection:
        post = (await connection.execute(text("SELECT author_user_id FROM discovery.looking_posts WHERE id=:id"), {"id": post_id})).mappings().one_or_none()
        if post is None or (post["author_user_id"] != viewer_id and await connection.scalar(text("SELECT 1 FROM discovery.looking_posts WHERE id=:id AND status='hidden'"), {"id": post_id})):
            raise LookingPostNotFound
        public = (await connection.execute(text("""
          SELECT q.id,q.question,q.answer,q.answered_at,q.created_at,
                 pr.public_id,pr.display_name,pr.avatar_asset_id
          FROM discovery.looking_post_questions q
          JOIN accounts.profiles pr ON pr.user_id=q.asker_user_id
          WHERE q.looking_post_id=:post AND q.answer IS NOT NULL
          ORDER BY q.answered_at,q.id
        """), {"post": post_id})).mappings().all()
        own = (await connection.execute(text("SELECT id,question,created_at FROM discovery.looking_post_questions WHERE looking_post_id=:post AND asker_user_id=:user AND answer IS NULL"), {"post": post_id, "user": viewer_id})).mappings().all()
        pending: list[dict[str, Any]] = [dict(row) for row in own]
        if post["author_user_id"] == viewer_id:
            author_rows = (await connection.execute(text("""
              SELECT q.id,q.question,q.created_at,pr.public_id,pr.display_name,pr.avatar_asset_id FROM discovery.looking_post_questions q
              JOIN accounts.profiles pr ON pr.user_id=q.asker_user_id WHERE q.looking_post_id=:post AND q.answer IS NULL ORDER BY q.created_at,q.id
            """), {"post": post_id})).mappings().all()
            pending = [{**dict(row), "asker": {"public_id": row["public_id"], "display_name": row["display_name"], "avatar_thumbnail_url": f"/api/profiles/{row['public_id']}/avatar?size=64" if row["avatar_asset_id"] else None}} for row in author_rows]
    public_items = [
        {
            "id": row["id"], "question": row["question"], "answer": row["answer"],
            "answered_at": row["answered_at"], "created_at": row["created_at"],
            "asker": {
                "public_id": row["public_id"], "display_name": row["display_name"],
                "avatar_thumbnail_url": f"/api/profiles/{row['public_id']}/avatar?size=64" if row["avatar_asset_id"] else None,
            },
        }
        for row in public
    ]
    viewer_can_ask = post["author_user_id"] != viewer_id and not own
    return {
        "items": public_items,
        "pending": pending,
        "viewer_can_ask": viewer_can_ask,
        "ask_block_reason": None if viewer_can_ask else (
            "author_cannot_ask" if post["author_user_id"] == viewer_id
            else "unanswered_question_exists"
        ),
    }


async def ask_question(engine: AsyncEngine, *, post_id: UUID, user_id: UUID, question: str, idempotency_key: UUID) -> UUID:
    question = _compact(question, 200)
    fingerprint = _fingerprint("question", post_id, question)
    try:
        async with engine.begin() as connection:
            previous = await _existing_request(connection, user_id, idempotency_key, fingerprint)
            if previous is not None:
                return previous
            post = (await connection.execute(text("SELECT author_user_id FROM discovery.looking_posts WHERE id=:id AND status='active' AND expires_at>now() FOR UPDATE"), {"id": post_id})).mappings().one_or_none()
            if post is None: raise LookingPostClosed("idea_closed")
            if post["author_user_id"] == user_id: raise LookingPostError("author_cannot_ask")
            question_id = uuid4()
            await connection.execute(text("INSERT INTO discovery.looking_post_questions (id,looking_post_id,asker_user_id,question) VALUES (:id,:post,:user,:question)"), {"id": question_id, "post": post_id, "user": user_id, "question": question})
            await _remember_request(connection, user_id, idempotency_key, "question", fingerprint, question_id)
            await _notify(connection, recipient=post["author_user_id"], kind="looking_post.question", title="Новый вопрос к идее", body="Откройте «Ищу людей», чтобы ответить.", subject_id=post_id, link=f"/app/looking/{post_id}")
            return question_id
    except IntegrityError as error: raise LookingPostConflict("unanswered_question_exists") from error


async def answer_question(engine: AsyncEngine, *, post_id: UUID, question_id: UUID, user_id: UUID, answer: str, idempotency_key: UUID) -> None:
    answer = _compact(answer, 300)
    fingerprint = _fingerprint("answer", post_id, question_id, answer)
    async with engine.begin() as connection:
        previous = await _existing_request(connection, user_id, idempotency_key, fingerprint)
        if previous is not None:
            return
        row = (await connection.execute(text("""
          SELECT q.asker_user_id FROM discovery.looking_post_questions q JOIN discovery.looking_posts p ON p.id=q.looking_post_id
          WHERE q.id=:question AND q.looking_post_id=:post AND q.answer IS NULL AND p.author_user_id=:user AND p.status='active' AND p.expires_at>now() FOR UPDATE
        """), {"question": question_id, "post": post_id, "user": user_id})).mappings().one_or_none()
        if row is None: raise LookingPostConflict("question_not_answerable")
        await connection.execute(text("UPDATE discovery.looking_post_questions SET answer=:answer,answered_at=now() WHERE id=:id"), {"answer": answer, "id": question_id})
        await _remember_request(connection, user_id, idempotency_key, "answer", fingerprint, question_id)
        await _notify(connection, recipient=row["asker_user_id"], kind="looking_post.answer", title="На ваш вопрос ответили", body="Откройте идею, чтобы прочитать ответ.", subject_id=post_id, link=f"/app/looking/{post_id}")


async def expire_looking_posts(engine: AsyncEngine) -> int:
    async with engine.begin() as connection:
        result = await connection.execute(text("""
          UPDATE discovery.looking_posts SET status='expired',closed_at=now(),delete_after=now()+interval '24 hours',version=version+1
          WHERE status='active' AND expires_at<=now() RETURNING id
        """))
        ids = [row[0] for row in result.all()]
        if ids:
            await connection.execute(text("UPDATE discovery.looking_post_questions SET delete_after=now()+interval '24 hours' WHERE looking_post_id = ANY(:ids) AND delete_after IS NULL"), {"ids": ids})
    return len(ids)


async def withdraw_looking_post(engine: AsyncEngine, *, post_id: UUID, user_id: UUID) -> None:
    async with engine.begin() as connection:
        result = await connection.execute(text("""
          UPDATE discovery.looking_posts SET status='hidden', closed_at=now(), delete_after=now()+interval '24 hours', version=version+1
          WHERE id=:id AND author_user_id=:user AND status='active' AND expires_at>now()
        """), {"id": post_id, "user": user_id})
        if not result.rowcount:
            raise LookingPostClosed("idea_closed")
        await connection.execute(text("UPDATE discovery.looking_post_questions SET delete_after=now()+interval '24 hours' WHERE looking_post_id=:id AND delete_after IS NULL"), {"id": post_id})


async def _notify(connection: Any, *, recipient: UUID, kind: str, title: str, body: str, subject_id: UUID, link: str) -> None:
    await connection.execute(text("""
      INSERT INTO communication.notifications (id,recipient_user_id,kind,title,body,subject_type,subject_id,deep_link)
      VALUES (:id,:recipient,:kind,:title,:body,'looking_post',:subject,:link)
    """), {"id": uuid4(), "recipient": recipient, "kind": kind, "title": title, "body": body, "subject": subject_id, "link": link})


def _fingerprint(action: str, *parts: object) -> str:
    return sha256("\x1f".join((action, *(str(part) for part in parts))).encode()).hexdigest()


async def _existing_request(connection: Any, user_id: UUID, key: UUID, fingerprint: str) -> UUID | None:
    # A missing row cannot be locked with FOR UPDATE.  Lock a stable hash first,
    # so two identical taps cannot both create a row before either inserts it.
    await connection.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": f"looking-post:{user_id}:{key}"})
    row = (await connection.execute(text("SELECT request_fingerprint, resource_id FROM discovery.looking_post_requests WHERE user_id=:user AND idempotency_key=:key FOR UPDATE"), {"user": user_id, "key": key})).mappings().one_or_none()
    if row is None:
        return None
    if row["request_fingerprint"] != fingerprint:
        raise LookingPostConflict("idempotency_key_reused")
    return row["resource_id"]


async def _remember_request(connection: Any, user_id: UUID, key: UUID, action: str, fingerprint: str, resource_id: UUID) -> None:
    await connection.execute(text("INSERT INTO discovery.looking_post_requests (user_id,idempotency_key,action,request_fingerprint,resource_id) VALUES (:user,:key,:action,:fingerprint,:resource)"), {"user": user_id, "key": key, "action": action, "fingerprint": fingerprint, "resource": resource_id})
