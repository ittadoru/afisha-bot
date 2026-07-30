from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from uuid import UUID, uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from afishabot.core.metrics import HTTP_REQUESTS

REQUEST_ID: ContextVar[str | None] = ContextVar("request_id", default=None)


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = _safe_request_id(request.headers.get("X-Request-ID"))
        token = REQUEST_ID.set(request_id)
        try:
            response = await call_next(request)
        finally:
            REQUEST_ID.reset(token)
        response.headers["X-Request-ID"] = request_id
        route = request.scope.get("route")
        route_path = getattr(route, "path", "unmatched")
        HTTP_REQUESTS.labels(
            method=request.method,
            route=str(route_path),
            status=str(response.status_code),
        ).inc()
        return response


def _safe_request_id(candidate: str | None) -> str:
    if candidate is not None:
        try:
            return str(UUID(candidate))
        except ValueError:
            pass
    return str(uuid4())
