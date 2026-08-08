"""HTTP contract for the short-lived "Looking for people" feed."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Cookie, Header, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from redis.asyncio import Redis
from redis.exceptions import RedisError

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
    cursor_at: Annotated[str | None, Query()] = None,
    cursor_id: Annotated[UUID | None, Query()] = None,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> dict[str, object]:
    _, _, engine = dependencies(request)
    viewer = await optional_viewer(request, token)
    cursor = None
    if cursor_at is not None and cursor_id is not None:
        from datetime import datetime

        try:
            cursor = (datetime.fromisoformat(cursor_at), cursor_id)
        except ValueError as error:
            raise HTTPException(status_code=422, detail="invalid_cursor") from error
    items, next_cursor = await looking_post_feed(
        engine, city_id=city_id, viewer_id=viewer, sort=sort, cursor=cursor, limit=limit
    )
    return {
        "items": items,
        "next_cursor": (
            {"at": next_cursor[0].isoformat(), "id": next_cursor[1]} if next_cursor else None
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
) -> dict[str, object]:
    settings, redis, engine = dependencies(request)
    validate_origin(request, settings)
    user_id = await mutation_user(request, token, csrf)
    await _limit(redis, user_id=user_id, action="create", maximum=5, seconds=3600)
    try:
        return await create_looking_post(engine, user_id=user_id, **body.model_dump())
    except LookingPostError as error:
        raise _error(error) from error


@router.put("/{post_id}/like")
async def like(
    request: Request, post_id: UUID,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    csrf: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
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
) -> Response:
    settings, redis, engine = dependencies(request)
    validate_origin(request, settings)
    user_id = await mutation_user(request, token, csrf)
    await _limit(redis, user_id=user_id, action="question", maximum=10, seconds=3600)
    try:
        await ask_question(engine, post_id=post_id, user_id=user_id, question=body.question)
    except LookingPostError as error:
        raise _error(error) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{post_id}/questions/{question_id}/answer", status_code=status.HTTP_204_NO_CONTENT)
async def answer(
    request: Request, post_id: UUID, question_id: UUID, body: AnswerRequest,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    csrf: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
) -> Response:
    settings, redis, engine = dependencies(request)
    validate_origin(request, settings)
    user_id = await mutation_user(request, token, csrf)
    await _limit(redis, user_id=user_id, action="answer", maximum=30, seconds=3600)
    try:
        await answer_question(engine, post_id=post_id, question_id=question_id, user_id=user_id, answer=body.answer)
    except LookingPostError as error:
        raise _error(error) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
