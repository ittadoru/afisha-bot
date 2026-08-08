"""HTTP contract for the short-lived "Looking for people" feed."""

import base64
import json
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Cookie, Header, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from afishabot.adapters.http.auth import CSRF_HEADER, SESSION_COOKIE
from afishabot.adapters.http.events import optional_viewer
from afishabot.adapters.http.profiles import (
    current_user,
    dependencies,
    mutation_user,
    validate_origin,
)
from afishabot.modules.discovery.application.looking_posts import (
    LookingPostConflict,
    LookingPostError,
    LookingPostNotFound,
    answer_question,
    ask_question,
    create_looking_post,
    looking_post_detail,
    looking_post_feed,
    questions_for_viewer,
    set_looking_post_like,
    withdraw_looking_post,
)

router = APIRouter(prefix="/looking-posts", tags=["looking-posts"])


class LookingPostRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    city_id: UUID
    category_id: UUID
    title: str = Field(min_length=1, max_length=30)
    body: str = Field(min_length=1, max_length=300)


class QuestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=200)


class AnswerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: str = Field(min_length=1, max_length=300)


class ReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=3, max_length=300)
    question_id: UUID | None = None


async def _limit(redis: Redis, *, user_id: UUID, action: str, maximum: int, seconds: int) -> None:
    key = f"abuse:looking:{action}:{user_id}"
    try:
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, seconds)
    except RedisError as error:
        raise HTTPException(status_code=503, detail="abuse_protection_unavailable") from error
    if count > maximum:
        raise HTTPException(status_code=429, detail="rate_limited")


def _error(error: LookingPostError) -> HTTPException:
    if isinstance(error, LookingPostNotFound):
        return HTTPException(status_code=404, detail="looking_post_not_found")
    if isinstance(error, LookingPostConflict):
        return HTTPException(status_code=409, detail=str(error))
    return HTTPException(status_code=422, detail=str(error))


@router.get("")
async def feed(
    request: Request,
    city_id: Annotated[UUID, Query()],
    sort: Annotated[Literal["new", "old", "popular"], Query()] = "new",
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    cursor: Annotated[str | None, Query()] = None,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> dict[str, object]:
    _, _, engine = dependencies(request)
    viewer = await optional_viewer(request, token)
    parsed_cursor = None
    if cursor is not None:
        try:
            data = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
            if data.get("city_id") != str(city_id) or data.get("sort") != sort:
                raise ValueError("cursor scope mismatch")
            parsed_cursor = (data.get("likes"), datetime.fromisoformat(data["at"]), UUID(data["id"]))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise HTTPException(status_code=422, detail="invalid_cursor") from error
    items, next_cursor = await looking_post_feed(
        engine, city_id=city_id, viewer_id=viewer, sort=sort, cursor=parsed_cursor, limit=limit
    )
    return {
        "items": items,
        "next_cursor": (
            base64.urlsafe_b64encode(json.dumps({"city_id": str(city_id), "sort": sort, "likes": next_cursor[0], "at": next_cursor[1].isoformat(), "id": str(next_cursor[2])}).encode()).decode().rstrip("=") if next_cursor else None
        ),
    }


@router.get("/{post_id}")
async def detail(
    request: Request,
    post_id: UUID,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> dict[str, object]:
    _, _, engine = dependencies(request)
    try:
        return await looking_post_detail(engine, post_id=post_id, viewer_id=await optional_viewer(request, token))
    except LookingPostError as error:
        raise _error(error) from error


@router.post("", status_code=status.HTTP_201_CREATED)
async def create(
    request: Request, body: LookingPostRequest,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    csrf: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
    idempotency_key: Annotated[UUID | None, Header(alias="Idempotency-Key")] = None,
) -> dict[str, object]:
    settings, redis, engine = dependencies(request)
    validate_origin(request, settings)
    user_id = await mutation_user(request, token, csrf)
    if idempotency_key is None:
        raise HTTPException(status_code=422, detail="idempotency_key_required")
    await _limit(redis, user_id=user_id, action="create", maximum=5, seconds=3600)
    try:
        return await create_looking_post(engine, user_id=user_id, idempotency_key=idempotency_key, **body.model_dump())
    except LookingPostError as error:
        raise _error(error) from error


@router.put("/{post_id}/like")
async def like(
    request: Request, post_id: UUID,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    csrf: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
    idempotency_key: Annotated[UUID | None, Header(alias="Idempotency-Key")] = None,
) -> dict[str, object]:
    settings, redis, engine = dependencies(request)
    validate_origin(request, settings)
    user_id = await mutation_user(request, token, csrf)
    await _limit(redis, user_id=user_id, action="like", maximum=120, seconds=3600)
    try:
        return await set_looking_post_like(engine, post_id=post_id, user_id=user_id, active=True)
    except LookingPostError as error:
        raise _error(error) from error


@router.delete("/{post_id}/like", status_code=status.HTTP_204_NO_CONTENT)
async def unlike(
    request: Request, post_id: UUID,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    csrf: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
) -> Response:
    settings, redis, engine = dependencies(request)
    validate_origin(request, settings)
    user_id = await mutation_user(request, token, csrf)
    await _limit(redis, user_id=user_id, action="like", maximum=120, seconds=3600)
    try:
        await set_looking_post_like(engine, post_id=post_id, user_id=user_id, active=False)
    except LookingPostError as error:
        raise _error(error) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{post_id}/questions")
async def questions(
    request: Request, post_id: UUID,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> dict[str, object]:
    _, _, engine = dependencies(request)
    user_id = await current_user(request, token)
    try:
        return await questions_for_viewer(engine, post_id=post_id, viewer_id=user_id)
    except LookingPostError as error:
        raise _error(error) from error


@router.post("/{post_id}/questions", status_code=status.HTTP_204_NO_CONTENT)
async def question(
    request: Request, post_id: UUID, body: QuestionRequest,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    csrf: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
    idempotency_key: Annotated[UUID | None, Header(alias="Idempotency-Key")] = None,
) -> Response:
    settings, redis, engine = dependencies(request)
    validate_origin(request, settings)
    user_id = await mutation_user(request, token, csrf)
    if idempotency_key is None:
        raise HTTPException(status_code=422, detail="idempotency_key_required")
    await _limit(redis, user_id=user_id, action="question", maximum=10, seconds=3600)
    try:
        await ask_question(engine, post_id=post_id, user_id=user_id, question=body.question, idempotency_key=idempotency_key)
    except LookingPostError as error:
        raise _error(error) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def withdraw(
    request: Request, post_id: UUID,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    csrf: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
) -> Response:
    settings, _, engine = dependencies(request)
    validate_origin(request, settings)
    user_id = await mutation_user(request, token, csrf)
    try:
        await withdraw_looking_post(engine, post_id=post_id, user_id=user_id)
    except LookingPostError as error:
        raise _error(error) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{post_id}/reports", status_code=status.HTTP_201_CREATED)
async def report(
    request: Request, post_id: UUID, body: ReportRequest,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    csrf: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
) -> dict[str, str]:
    settings, redis, engine = dependencies(request)
    validate_origin(request, settings)
    user_id = await mutation_user(request, token, csrf)
    await _limit(redis, user_id=user_id, action="report", maximum=10, seconds=3600)
    async with engine.begin() as connection:
        post = (await connection.execute(text("SELECT author_user_id FROM discovery.looking_posts WHERE id=:id AND status='active'"), {"id": post_id})).mappings().one_or_none()
        if post is None: raise HTTPException(status_code=404, detail="looking_post_not_found")
        if post["author_user_id"] == user_id: raise HTTPException(status_code=422, detail="cannot_report_self")
        if body.question_id is not None:
            valid = await connection.scalar(text("SELECT 1 FROM discovery.looking_post_questions WHERE id=:question AND looking_post_id=:post AND answer IS NOT NULL"), {"question": body.question_id, "post": post_id})
            if valid is None: raise HTTPException(status_code=422, detail="invalid_question")
        try:
            await connection.execute(text("""INSERT INTO trust_safety.profile_reports
              (id,reporter_user_id,subject_user_id,reason,comment,source_question_id,source_looking_post_id)
              VALUES (:id,:reporter,:subject,'other',:comment,:question,:post)"""), {"id": uuid4(), "reporter": user_id, "subject": post["author_user_id"], "comment": body.reason.strip(), "question": body.question_id, "post": post_id})
        except IntegrityError as error:
            # Existing open report is a successful idempotent outcome for the UI.
            raise HTTPException(status_code=409, detail="report_already_open") from error
    return {"status": "accepted"}


@router.post("/{post_id}/questions/{question_id}/answer", status_code=status.HTTP_204_NO_CONTENT)
async def answer(
    request: Request, post_id: UUID, question_id: UUID, body: AnswerRequest,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    csrf: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
    idempotency_key: Annotated[UUID | None, Header(alias="Idempotency-Key")] = None,
) -> Response:
    settings, redis, engine = dependencies(request)
    validate_origin(request, settings)
    user_id = await mutation_user(request, token, csrf)
    if idempotency_key is None:
        raise HTTPException(status_code=422, detail="idempotency_key_required")
    await _limit(redis, user_id=user_id, action="answer", maximum=30, seconds=3600)
    try:
        await answer_question(engine, post_id=post_id, question_id=question_id, user_id=user_id, answer=body.answer, idempotency_key=idempotency_key)
    except LookingPostError as error:
        raise _error(error) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
