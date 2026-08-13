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


def test_case_decision_constraint_accepts_typed_actions() -> None:
    source = Path("migrations/versions/0037_expand_case_decisions.py").read_text(
        encoding="utf-8"
    )
    for action in ("hide_component", "hold_for_correction", "hide_subject"):
        assert action in source
    assert "DELETE FROM trust_safety.case_decisions" not in source
    assert "SET decision_type='hide_content'" in source


def test_case_audit_uses_typed_json_and_subject_conflict() -> None:
    source = Path(
        "src/afishabot/modules/trust_safety/application/case_moderation.py"
    ).read_text(encoding="utf-8")
    assert "CAST(:details AS jsonb)" in source
    assert 'CaseModerationError("subject_action_conflict")' in source
    assert "status='hidden',closed_at=now()" in source
    assert "delete_subject" in source


def test_test_queue_reset_is_ordered_and_irreversible() -> None:
    source = Path(
        "migrations/versions/0038_reset_test_moderation_cases.py"
    ).read_text(encoding="utf-8")
    ordered_tables = (
        "profile_restrictions",
        "profile_violations",
        "case_decisions",
        "appeals",
        "case_timeline_entries",
        "reports",
        "moderation_cases",
        "profile_reports",
    )
    positions = [
        source.index(f"DELETE FROM trust_safety.{table}")
        for table in ordered_tables
    ]
    assert positions == sorted(positions)
    assert "def downgrade()" in source and "pass" in source


def test_reversible_sanctions_keep_media_until_appeal_is_decided() -> None:
    migration = Path(
        "migrations/versions/0039_reversible_moderation_sanctions.py"
    ).read_text(encoding="utf-8")
    source = Path(
        "src/afishabot/modules/trust_safety/application/case_moderation.py"
    ).read_text(encoding="utf-8")
    assert "moderation_sanctions" in migration
    assert "moderation_hidden" in migration
    assert "answer_hidden_by_case_id" in migration
    assert "state='moderation_hidden'" in source
    assert "_reverse_sanction" in source


def test_staff_evidence_uses_authenticated_immutable_media_route() -> None:
    backend = Path("src/afishabot/adapters/admin/http.py").read_text(encoding="utf-8")
    frontend = Path("frontend/src/admin-app.tsx").read_text(encoding="utf-8")
    styles = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert '@router.get("/moderation/evidence/{case_public_id}")' in backend
    assert "r.evidence_snapshot->>'value'" in backend
    assert "/api/admin/moderation/evidence/${detail.public_id}" in frontend
    assert "setSelected(null);" in frontend
    assert ".report-screen { width: 100%; height: 100%; min-height: 0;" in styles


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
