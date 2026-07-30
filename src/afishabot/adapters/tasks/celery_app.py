from celery import Celery

from afishabot.core.config import Settings


def create_celery_app(settings: Settings | None = None) -> Celery:
    resolved = settings or Settings()
    application = Celery("afishabot", broker=resolved.redis_dsn())
    application.conf.update(
        beat_schedule={},
        broker_connection_retry_on_startup=True,
        result_backend=None,
        task_ignore_result=True,
        task_serializer="json",
        accept_content=["json"],
        timezone="Europe/Moscow",
        enable_utc=True,
    )
    return application


celery_app = create_celery_app()
