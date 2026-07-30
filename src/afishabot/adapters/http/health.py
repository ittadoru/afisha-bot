import asyncio
from typing import Literal, cast

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncEngine

from afishabot.core.config import Settings
from afishabot.core.database import database_is_ready

router = APIRouter(tags=["platform"])


class HealthResponse(BaseModel):
    status: Literal["ok", "unavailable"]


@router.get("/health/live", response_model=HealthResponse)
async def liveness() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get(
    "/health/ready",
    response_model=HealthResponse,
    responses={503: {"model": HealthResponse}},
)
async def readiness(request: Request, response: Response) -> HealthResponse:
    settings = cast(Settings, request.app.state.settings)
    engine = cast(AsyncEngine, request.app.state.database_engine)
    try:
        ready = await asyncio.wait_for(
            database_is_ready(engine),
            timeout=settings.readiness_timeout_seconds,
        )
    except TimeoutError:
        ready = False
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(status="unavailable")
    return HealthResponse(status="ok")
