from datetime import UTC, datetime
from typing import Any

import pytest

from afishabot.modules.trust_safety.application.case_moderation import (
    _direction,
    moderation_queue,
)


class _QueueResult:
    def mappings(self) -> "_QueueResult":
        return self

    def all(self) -> list[dict[str, Any]]:
        return []


class _QueueConnection:
    def __init__(self) -> None:
        self.statement = ""
        self.parameters: dict[str, Any] = {}

    async def __aenter__(self) -> "_QueueConnection":
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def execute(
        self, statement: object, parameters: dict[str, Any]
    ) -> _QueueResult:
        self.statement = str(statement)
        self.parameters = parameters
        return _QueueResult()


class _QueueEngine:
    def __init__(self) -> None:
        self.connection = _QueueConnection()

    def connect(self) -> _QueueConnection:
        return self.connection


def test_profile_components_have_independent_policy_directions() -> None:
    assert _direction("avatar") == "profile_media"
    assert _direction("background") == "profile_media"
    assert _direction("display_name") == "profile_text"
    assert _direction("bio") == "profile_text"
    assert _direction(None) is None


def test_staff_moderation_migration_contains_required_safety_guards() -> None:
    source = open(
        "migrations/versions/0034_staff_case_moderation.py", encoding="utf-8"
    ).read()
    assert "case_decisions" in source
    assert "idempotency_key uuid NOT NULL UNIQUE" in source
    assert "profile_violations" in source
    assert "profile_restrictions" in source
    assert "180 days" not in source  # policy window belongs to application logic


@pytest.mark.asyncio
async def test_report_queue_omits_null_cursor_parameter() -> None:
    engine = _QueueEngine()

    await moderation_queue(engine, queue="reports", limit=51)  # type: ignore[arg-type]

    assert ":before" not in engine.connection.statement
    assert engine.connection.parameters == {"limit": 51}


@pytest.mark.asyncio
async def test_appeal_queue_uses_typed_datetime_only_when_provided() -> None:
    engine = _QueueEngine()
    before = datetime(2026, 8, 11, tzinfo=UTC)

    await moderation_queue(  # type: ignore[arg-type]
        engine, queue="appeals", limit=20, before=before
    )

    assert "a.created_at<:before" in engine.connection.statement
    assert engine.connection.parameters == {"limit": 20, "before": before}
