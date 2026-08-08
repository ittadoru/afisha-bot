from fastapi import FastAPI
from prometheus_client import (
    make_asgi_app,  # pyright: ignore[reportUnknownVariableType]
)

from afishabot.adapters.admin.http import router as admin_router
from afishabot.adapters.http.auth import router as auth_router
from afishabot.adapters.http.chat import router as chat_router
from afishabot.adapters.http.events import router as events_router
from afishabot.adapters.http.geo import router as geo_router
from afishabot.adapters.http.health import router as health_router
from afishabot.adapters.http.looking_posts import router as looking_posts_router
from afishabot.adapters.http.media import router as media_router
from afishabot.adapters.http.middleware import RequestContextMiddleware
from afishabot.adapters.http.profiles import router as profiles_router
from afishabot.core.config import Settings
from afishabot.core.lifespan import lifespan
from afishabot.modules.discovery.infrastructure.nominatim import (
    NominatimReverseGeocoder,
)


def create_app(settings: Settings | None = None) -> FastAPI:
    application = FastAPI(
        title="Afisha API",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    resolved_settings = settings or Settings()
    application.state.settings = resolved_settings
    application.state.reverse_geocoder = NominatimReverseGeocoder(
        resolved_settings.nominatim_url,
        resolved_settings.nominatim_timeout_seconds,
    )
    application.add_middleware(RequestContextMiddleware)
    application.include_router(health_router)
    application.include_router(geo_router)
    application.include_router(auth_router)
    application.include_router(events_router)
    application.include_router(chat_router)
    application.include_router(looking_posts_router)
    application.include_router(profiles_router)
    application.include_router(media_router)
    application.include_router(admin_router)
    application.mount(
        "/metrics",
        make_asgi_app(),  # pyright: ignore[reportUnknownArgumentType]
    )
    return application
