import asyncio

from celery import Celery

from afishabot.core.config import Settings
from afishabot.core.database import create_database_engine
from afishabot.modules.events.application.manage_event import finish_due_events


def create_celery_app(settings: Settings | None = None) -> Celery:
    resolved = settings or Settings()
    application = Celery("afishabot", broker=resolved.redis_dsn())
    application.conf.update(  # pyright: ignore[reportUnknownMemberType]
        beat_schedule={
            "finish-due-events": {
                "task": "afishabot.events.finish_due",
                "schedule": 60.0,
            },
        },
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


@celery_app.task(name="afishabot.events.finish_due")
def finish_due_events_task() -> int:
    async def run() -> int:
        engine = create_database_engine(Settings().database_dsn())
        try:
            return await finish_due_events(engine)
        finally:
            await engine.dispose()

    return asyncio.run(run())
