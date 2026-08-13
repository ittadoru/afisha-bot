import asyncio

from celery import Celery

from afishabot.core.config import Settings
from afishabot.core.database import create_database_engine
from afishabot.modules.communication.application.telegram_dispatch import (
    dispatch_telegram_notifications,
)
from afishabot.modules.discovery.application.looking_posts import expire_looking_posts
from afishabot.modules.events.application.manage_event import finish_due_events
from afishabot.modules.media.application.storage_analysis import estimate_savings
from afishabot.modules.trust_safety.application.case_moderation import (
    confirm_due_violations,
    finalize_due_event_moderation,
    purge_expired_evidence,
)


def create_celery_app(settings: Settings | None = None) -> Celery:
    resolved = settings or Settings()
    application = Celery("afishabot", broker=resolved.redis_dsn())
    application.conf.update(  # pyright: ignore[reportUnknownMemberType]
        beat_schedule={
            "finish-due-events": {
                "task": "afishabot.events.finish_due",
                "schedule": 60.0,
            },
            "expire-looking-posts": {
                "task": "afishabot.discovery.expire_looking_posts",
                "schedule": 60.0,
            },
            "dispatch-telegram-notifications": {
                "task": "afishabot.communication.dispatch_tg",
                "schedule": 30.0,
            },
            "confirm-profile-violations": {
                "task": "afishabot.trust_safety.confirm_profile_violations",
                "schedule": 60.0,
            },
            "finalize-event-moderation": {
                "task": "afishabot.trust_safety.finalize_event_moderation",
                "schedule": 60.0,
            },
            "purge-expired-moderation-evidence": {
                "task": "afishabot.trust_safety.purge_expired_evidence",
                "schedule": 86400.0,
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


@celery_app.task(name="afishabot.discovery.expire_looking_posts")
def expire_looking_posts_task() -> int:
    async def run() -> int:
        engine = create_database_engine(Settings().database_dsn())
        try:
            return await expire_looking_posts(engine)
        finally:
            await engine.dispose()

    return asyncio.run(run())


@celery_app.task(name="afishabot.communication.dispatch_tg")
def dispatch_tg_notifications_task() -> int:
    async def run() -> int:
        engine = create_database_engine(Settings().database_dsn())
        try:
            return await dispatch_telegram_notifications(engine)
        finally:
            await engine.dispose()

    return asyncio.run(run())


@celery_app.task(name="afishabot.trust_safety.confirm_profile_violations")
def confirm_profile_violations_task() -> int:
    async def run() -> int:
        engine = create_database_engine(Settings().database_dsn())
        try:
            return await confirm_due_violations(engine)
        finally:
            await engine.dispose()

    return asyncio.run(run())


@celery_app.task(name="afishabot.trust_safety.finalize_event_moderation")
def finalize_event_moderation_task() -> int:
    async def run() -> int:
        engine = create_database_engine(Settings().database_dsn())
        try:
            return await finalize_due_event_moderation(engine)
        finally:
            await engine.dispose()

    return asyncio.run(run())


@celery_app.task(name="afishabot.trust_safety.purge_expired_evidence")
def purge_expired_evidence_task() -> int:
    async def run() -> int:
        settings = Settings()
        engine = create_database_engine(settings.database_dsn())
        try:
            return await purge_expired_evidence(engine, settings.media_root)
        finally:
            await engine.dispose()

    return asyncio.run(run())


@celery_app.task(name="afishabot.media.estimate_storage_savings")
def estimate_storage_savings_task(job_id: str) -> None:
    async def run() -> None:
        settings = Settings()
        engine = create_database_engine(settings.database_dsn())
        try:
            from uuid import UUID

            await estimate_savings(
                engine, media_root=settings.media_root, job_id=UUID(job_id)
            )
        finally:
            await engine.dispose()

    asyncio.run(run())
