from fastapi import FastAPI
from prometheus_client import make_asgi_app

from afishabot.adapters.http.health import router as health_router
from afishabot.adapters.http.middleware import RequestContextMiddleware
from afishabot.core.config import Settings
from afishabot.core.lifespan import lifespan


def create_app(settings: Settings | None = None) -> FastAPI:
    application = FastAPI(
        title="Afisha API",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    application.state.settings = settings or Settings()
    application.add_middleware(RequestContextMiddleware)
    application.include_router(health_router)
    application.mount("/metrics", make_asgi_app())
    return application
