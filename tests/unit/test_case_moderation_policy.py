from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from afishabot.adapters.http.safety import ALLOWED_COMPONENTS
from afishabot.modules.trust_safety.application.case_moderation import (
    _available_actions,
    _direction,
    _subject_projection,
    moderation_queue,
)


class _ProjectionResult:
    def mappings(self) -> _ProjectionResult:
        return self

    def one_or_none(self) -> dict[str, str]:
        return {"title": "Прогулка", "status": "published"}


class _ProjectionConnection:
    def __init__(self) -> None:
        self.statement = ""

    async def __aenter__(self) -> _ProjectionConnection:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    def begin_nested(self) -> _ProjectionConnection:
        return self

    async def execute(
        self, statement: object, _parameters: object
    ) -> _ProjectionResult:
        self.statement = str(statement)
        return _ProjectionResult()


class _QueueResult:
    def mappings(self) -> _QueueResult:
        return self

    def all(self) -> list[dict[str, Any]]:
        return []


class _QueueConnection:
    def __init__(self) -> None:
        self.statement = ""
        self.parameters: dict[str, Any] = {}

    async def __aenter__(self) -> _QueueConnection:
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


def test_report_components_are_explicit_for_every_supported_subject() -> None:
    assert "attendance" not in ALLOWED_COMPONENTS
    assert ALLOWED_COMPONENTS["event"] == {
        "photo",
        "title",
        "description",
        "schedule",
        "location",
        "whole",
    }
    assert ALLOWED_COMPONENTS["chat_message"] == {"message"}
    assert ALLOWED_COMPONENTS["q_and_a_answer"] == {"answer"}


def test_required_event_text_is_held_for_correction() -> None:
    assert _available_actions("event", "description") == [
        "dismiss",
        "hold_for_correction",
        "hide_subject",
    ]
    assert _available_actions("event", "photo") == ["dismiss", "hide_component"]


def test_staff_moderation_migration_contains_required_safety_guards() -> None:
    source = Path("migrations/versions/0034_staff_case_moderation.py").read_text(
        encoding="utf-8"
    )
    assert "case_decisions" in source
    assert "idempotency_key uuid NOT NULL UNIQUE" in source
    assert "profile_violations" in source
    assert "profile_restrictions" in source
    assert "180 days" not in source  # policy window belongs to application logic


def test_typed_evidence_migration_resets_prototype_cases_and_hides_chat() -> None:
    source = Path("migrations/versions/0036_typed_moderation_evidence.py").read_text(
        encoding="utf-8"
    )
    assert "DELETE FROM trust_safety.moderation_cases" in source
    assert source.index("DELETE FROM trust_safety.reports") < source.index(
        "DELETE FROM trust_safety.moderation_cases"
    )
    assert "hidden_by_case_id" in source


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


@pytest.mark.asyncio
async def test_event_case_projection_reads_title_from_revision() -> None:
    connection = _ProjectionConnection()

    result = await _subject_projection(  # type: ignore[arg-type]
        connection,
        {"subject_type": "event", "subject_id": "event-id"},
    )

    assert result == {"title": "Прогулка", "status": "published"}
    assert "events.event_revisions" in connection.statement
    assert (
        "COALESCE(e.approved_revision_id,e.current_revision_id)" in connection.statement
    )
