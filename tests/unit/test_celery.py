from collections.abc import Mapping
from typing import cast

from afishabot.adapters.tasks.celery_app import create_celery_app
from afishabot.core.config import Settings


def test_celery_has_no_results_and_only_approved_schedule(settings: Settings) -> None:
    application = create_celery_app(settings)
    configuration = cast(
        Mapping[str, object],
        application.conf,  # pyright: ignore[reportUnknownMemberType]
    )

    assert configuration["result_backend"] is None
    assert configuration["beat_schedule"] == {
        "finish-due-events": {
            "task": "afishabot.events.finish_due",
            "schedule": 60.0,
        }
        ,"expire-looking-posts": {
            "task": "afishabot.discovery.expire_looking_posts",
            "schedule": 60.0,
        }
    }
    assert configuration["task_ignore_result"] is True
