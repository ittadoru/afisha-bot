"""HTTP routes for the event chat."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Cookie, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field
from redis.asyncio import Redis
from redis.exceptions import RedisError

from afishabot.adapters.http.auth import CSRF_HEADER, SESSION_COOKIE
from afishabot.adapters.http.profiles import (
    current_user,
    dependencies,
    mutation_user,
    validate_origin,
)
from afishabot.modules.communication.application.event_chat import (
    ChatClosed,
    ChatError,
    ChatForbidden,
    ChatIdempotencyReused,
    EventNotActive,
    list_messages,
    send_message,
    set_chat_enabled,
)

router = APIRouter(prefix="/events", tags=["chat"])


class ChatMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: str = Field(min_length=1, max_length=500)


class ChatStateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool


async def _chat_limit(redis: Redis, *, event_id: UUID, user_id: UUID) -> None:
    key = f"abuse:event-chat:{event_id}:{user_id}"
    try:
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, 3)
    except RedisError as error:
        raise HTTPException(
            status_code=503, detail="abuse_protection_unavailable"
        ) from error
    if count > 1:
        raise HTTPException(status_code=429, detail="rate_limited")


def _error(error: ChatError) -> HTTPException:
    if isinstance(error, ChatForbidden):
        return HTTPException(status_code=403, detail=str(error))
    if isinstance(error, ChatClosed):
        return HTTPException(status_code=403, detail="chat_closed")
    if isinstance(error, EventNotActive):
        return HTTPException(status_code=404, detail="event_not_found")
    if isinstance(error, ChatIdempotencyReused):
        return HTTPException(status_code=409, detail="idempotency_key_reused")
    return HTTPException(status_code=422, detail=str(error))


@router.get("/{event_id}/chat")
async def messages(
    request: Request,
    event_id: UUID,
    after: Annotated[UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 200,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> dict[str, object]:
    _, _, engine = dependencies(request)
    user_id = await current_user(request, token)
    items, has_more = await list_messages(
        engine, event_id=event_id, viewer_id=user_id, after=after, limit=limit
    )
    return {"items": items, "has_more": has_more}


@router.post("/{event_id}/chat", status_code=status.HTTP_201_CREATED)
async def send(
    request: Request,
    event_id: UUID,
    body: ChatMessageRequest,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    csrf: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
    idempotency_key: Annotated[UUID | None, Header(alias="Idempotency-Key")] = None,
) -> dict[str, object]:
    settings, redis, engine = dependencies(request)
    validate_origin(request, settings)
    user_id = await mutation_user(request, token, csrf)
    if idempotency_key is None:
        raise HTTPException(status_code=422, detail="idempotency_key_required")
    await _chat_limit(redis, event_id=event_id, user_id=user_id)
    try:
        message = await send_message(
            engine,
            event_id=event_id,
            user_id=user_id,
            body=body.body,
            idempotency_key=idempotency_key,
        )
    except ChatError as error:
        raise _error(error) from error
    return {"message": message}


@router.put("/{event_id}/chat")
async def set_state(
    request: Request,
    event_id: UUID,
    body: ChatStateRequest,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    csrf: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
) -> dict[str, object]:
    settings, _, engine = dependencies(request)
    validate_origin(request, settings)
    user_id = await mutation_user(request, token, csrf)
    try:
        enabled = await set_chat_enabled(
            engine, event_id=event_id, user_id=user_id, enabled=body.enabled
        )
    except ChatError as error:
        raise _error(error) from error
    return {"chat_enabled": enabled}
