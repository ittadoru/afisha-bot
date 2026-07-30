from afishabot.adapters.tasks.celery_app import create_celery_app
from afishabot.core.config import Settings


def test_celery_has_no_results_or_business_schedule(settings: Settings) -> None:
    application = create_celery_app(settings)

    assert application.conf.result_backend is None
    assert application.conf.beat_schedule == {}
    assert application.conf.task_ignore_result is True
