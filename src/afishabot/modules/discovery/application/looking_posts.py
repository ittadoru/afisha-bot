"""LookingPost feed and Q&A use cases.

The module exposes only safe projections; question ownership is checked before
the private asker identity is ever selected.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine


Sort = Literal["new", "old", "popular"]


class LookingPostError(Exception):
    pass


class LookingPostNotFound(LookingPostError):
    pass


class LookingPostConflict(LookingPostError):
    pass


def _compact(value: str, maximum: int) -> str:
    result = " ".join(value.split())
    if not result or len(result) > maximum or any(ord(char) < 32 for char in result):
        raise LookingPostError("invalid_text")
    return result


async def create_looking_post(
    engine: AsyncEngine, *, user_id: UUID, city_id: UUID, category_id: UUID,
    title: str, body: str,
) -> dict[str, Any]:
    title = _compact(title, 30); body = _compact(body, 300)
    post_id = uuid4()
    async with engine.begin() as connection:
        city = await connection.scalar(text("SELECT 1 FROM discovery.cities WHERE id=:id AND is_active AND looking_posts_enabled"), {"id": city_id})
        category = await connection.scalar(text("SELECT 1 FROM discovery.categories WHERE id=:id AND is_active AND organizer_selectable AND NOT is_special"), {"id": category_id})
        if city is None: raise LookingPostError("city_not_available")
        if category is None: raise LookingPostError("category_not_available")
        await connection.execute(text("""
            INSERT INTO discovery.looking_posts (id,author_user_id,city_id,category_id,title,body)
            VALUES (:id,:user,:city,:category,:title,:body)
        """), {"id": post_id, "user": user_id, "city": city_id, "category": category_id, "title": title, "body": body})
    return await looking_post_detail(engine, post_id=post_id, viewer_id=user_id)


async def looking_post_feed(
    engine: AsyncEngine, *, city_id: UUID, viewer_id: UUID | None, sort: Sort,
    cursor: tuple[datetime, UUID] | None, limit: int,
) -> tuple[list[dict[str, Any]], tuple[datetime, UUID] | None]:
    if sort == "popular":
        order = "like_count DESC, p.created_at DESC, p.id DESC"; cursor_sql = ""
    elif sort == "old":
        order = "p.created_at ASC, p.id ASC"; cursor_sql = "AND (p.created_at,p.id) > (:at,:id)" if cursor else ""
    else:
        order = "p.created_at DESC, p.id DESC"; cursor_sql = "AND (p.created_at,p.id) < (:at,:id)" if cursor else ""
    params: dict[str, Any] = {"city": city_id, "viewer": viewer_id, "limit": limit + 1}
    if cursor: params.update(at=cursor[0], id=cursor[1])
    async with engine.connect() as connection:
        rows = (await connection.execute(text(f"""
            SELECT p.id,p.author_user_id,p.title,p.body,p.status,p.created_at,p.expires_at,
                   p.pending_event_id,p.converted_event_id,c.name AS city,cat.name AS category,
                   pr.public_id,pr.display_name,pr.avatar_asset_id,
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
            WHERE p.city_id=:city AND p.status='active' AND p.expires_at>now() {cursor_sql}
            ORDER BY {order} LIMIT :limit
        """), params)).mappings().all()
    items = [_feed_item(row, viewer_id) for row in rows[:limit]]
    last = rows[limit - 1] if len(rows) > limit else None
    return items, ((last["created_at"], last["id"]) if last else None)


def _feed_item(row: Any, viewer_id: UUID | None) -> dict[str, Any]:
    author = row["author_user_id"] == viewer_id
    return {"id": row["id"], "title": row["title"], "body": row["body"], "status": row["status"], "created_at": row["created_at"], "expires_at": row["expires_at"], "city": row["city"], "category": row["category"], "like_count": int(row["like_count"] or 0), "question_count": int(row["question_count"] or 0), "viewer_liked": bool(row["viewer_liked"]) if viewer_id else False, "is_author": author, "pending_event_id": row["pending_event_id"] if author else None, "converted_event_id": row["converted_event_id"], "author": {"public_id": row["public_id"], "display_name": row["display_name"], "avatar_url": f"/api/profiles/{row['public_id']}/avatar" if row["avatar_asset_id"] else None}}


async def looking_post_detail(engine: AsyncEngine, *, post_id: UUID, viewer_id: UUID | None) -> dict[str, Any]:
    async with engine.connect() as connection:
        row = (await connection.execute(text("""
            SELECT p.id,p.author_user_id,p.title,p.body,p.status,p.created_at,p.expires_at,p.pending_event_id,p.converted_event_id,
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
    return _feed_item(row, viewer_id)


async def set_looking_post_like(engine: AsyncEngine, *, post_id: UUID, user_id: UUID, active: bool) -> dict[str, Any]:
    async with engine.begin() as connection:
        post = (await connection.execute(text("SELECT author_user_id FROM discovery.looking_posts WHERE id=:id AND status='active' AND expires_at>now() FOR UPDATE"), {"id": post_id})).mappings().one_or_none()
        if post is None: raise LookingPostNotFound
        if post["author_user_id"] == user_id: raise LookingPostError("author_cannot_like")
        await connection.execute(text("""
            INSERT INTO discovery.looking_post_likes (looking_post_id,user_id,active) VALUES (:post,:user,:active)
            ON CONFLICT (looking_post_id,user_id) DO UPDATE SET active=EXCLUDED.active,updated_at=now()
        """), {"post": post_id, "user": user_id, "active": active})
        count = await connection.scalar(text("SELECT count(*) FROM discovery.looking_post_likes WHERE looking_post_id=:post AND active"), {"post": post_id})
    return {"liked": active, "like_count": int(count or 0)}


async def questions_for_viewer(engine: AsyncEngine, *, post_id: UUID, viewer_id: UUID) -> dict[str, list[dict[str, Any]]]:
    async with engine.connect() as connection:
        post = (await connection.execute(text("SELECT author_user_id FROM discovery.looking_posts WHERE id=:id"), {"id": post_id})).mappings().one_or_none()
        if post is None: raise LookingPostNotFound
        public = (await connection.execute(text("SELECT id,question,answer,answered_at,created_at FROM discovery.looking_post_questions WHERE looking_post_id=:post AND answer IS NOT NULL ORDER BY answered_at,id"), {"post": post_id})).mappings().all()
        own = (await connection.execute(text("SELECT id,question,created_at FROM discovery.looking_post_questions WHERE looking_post_id=:post AND asker_user_id=:user AND answer IS NULL"), {"post": post_id, "user": viewer_id})).mappings().all()
        pending: list[dict[str, Any]] = [dict(row) for row in own]
        if post["author_user_id"] == viewer_id:
            author_rows = (await connection.execute(text("""
              SELECT q.id,q.question,q.created_at,pr.public_id,pr.display_name,pr.avatar_asset_id FROM discovery.looking_post_questions q
              JOIN accounts.profiles pr ON pr.user_id=q.asker_user_id WHERE q.looking_post_id=:post AND q.answer IS NULL ORDER BY q.created_at,q.id
            """), {"post": post_id})).mappings().all()
            pending = [{**dict(row), "asker": {"public_id": row["public_id"], "display_name": row["display_name"], "avatar_url": f"/api/profiles/{row['public_id']}/avatar" if row["avatar_asset_id"] else None}} for row in author_rows]
    return {"items": [dict(row) for row in public], "pending": pending}


async def ask_question(engine: AsyncEngine, *, post_id: UUID, user_id: UUID, question: str) -> None:
    question = _compact(question, 200)
    try:
        async with engine.begin() as connection:
            post = (await connection.execute(text("SELECT author_user_id FROM discovery.looking_posts WHERE id=:id AND status='active' AND expires_at>now() FOR UPDATE"), {"id": post_id})).mappings().one_or_none()
            if post is None: raise LookingPostNotFound
            if post["author_user_id"] == user_id: raise LookingPostError("author_cannot_ask")
            await connection.execute(text("INSERT INTO discovery.looking_post_questions (id,looking_post_id,asker_user_id,question) VALUES (:id,:post,:user,:question)"), {"id": uuid4(), "post": post_id, "user": user_id, "question": question})
            await _notify(connection, recipient=post["author_user_id"], kind="looking_post.question", title="Новый вопрос к идее", body="Откройте «Ищу людей», чтобы ответить.", subject_id=post_id, link=f"/app/looking/{post_id}")
    except IntegrityError as error: raise LookingPostConflict("unanswered_question_exists") from error


async def answer_question(engine: AsyncEngine, *, post_id: UUID, question_id: UUID, user_id: UUID, answer: str) -> None:
    answer = _compact(answer, 300)
    async with engine.begin() as connection:
        row = (await connection.execute(text("""
          SELECT q.asker_user_id FROM discovery.looking_post_questions q JOIN discovery.looking_posts p ON p.id=q.looking_post_id
          WHERE q.id=:question AND q.looking_post_id=:post AND q.answer IS NULL AND p.author_user_id=:user AND p.status='active' AND p.expires_at>now() FOR UPDATE
        """), {"question": question_id, "post": post_id, "user": user_id})).mappings().one_or_none()
        if row is None: raise LookingPostConflict("question_not_answerable")
        await connection.execute(text("UPDATE discovery.looking_post_questions SET answer=:answer,answered_at=now() WHERE id=:id"), {"answer": answer, "id": question_id})
        await _notify(connection, recipient=row["asker_user_id"], kind="looking_post.answer", title="На ваш вопрос ответили", body="Откройте идею, чтобы прочитать ответ.", subject_id=post_id, link=f"/app/looking/{post_id}")


async def expire_looking_posts(engine: AsyncEngine) -> int:
    async with engine.begin() as connection:
        result = await connection.execute(text("""
          UPDATE discovery.looking_posts SET status='expired',closed_at=now(),delete_after=now()+interval '24 hours',version=version+1
          WHERE status='active' AND expires_at<=now() RETURNING id
        """))
    return len(result.all())


async def _notify(connection: Any, *, recipient: UUID, kind: str, title: str, body: str, subject_id: UUID, link: str) -> None:
    await connection.execute(text("""
      INSERT INTO communication.notifications (id,recipient_user_id,kind,title,body,subject_type,subject_id,deep_link)
      VALUES (:id,:recipient,:kind,:title,:body,'looking_post',:subject,:link)
    """), {"id": uuid4(), "recipient": recipient, "kind": kind, "title": title, "body": body, "subject": subject_id, "link": link})
