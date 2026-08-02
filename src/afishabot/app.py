from fastapi import FastAPI
from prometheus_client import make_asgi_app

from afishabot.adapters.http.geo import router as geo_router
from afishabot.adapters.http.health import router as health_router
from afishabot.adapters.http.middleware import RequestContextMiddleware
from afishabot.core.config import Settings
from afishabot.core.lifespan import lifespan
from afishabot.modules.discovery.infrastructure.nominatim import NominatimReverseGeocoder


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
    application.mount("/metrics", make_asgi_app())
    return application
