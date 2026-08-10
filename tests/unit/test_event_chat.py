import uuid
from datetime import UTC, datetime

from asyncpg.pgproto.pgproto import UUID as PgUUID

from afishabot.modules.communication.application.event_chat import (
    _active_episode,
    _message_payload,
)


class _FakeConnection:
    def __init__(self, result: object) -> None:
        self._result = result

    async def scalar(self, *args: object, **kwargs: object) -> object:
        return self._result


async def test_active_episode_returns_asyncpg_uuid_unchanged() -> None:
    raw = PgUUID(str(uuid.uuid4()))
    connection = _FakeConnection(raw)
    result = await _active_episode(connection, uuid.uuid4(), uuid.uuid4())
    assert result is raw


async def test_active_episode_returns_none_when_no_episode() -> None:
    connection = _FakeConnection(None)
    result = await _active_episode(connection, uuid.uuid4(), uuid.uuid4())
    assert result is None


class _MappingResult:
    def __init__(self, row: dict[str, object]) -> None:
        self._row = row

    def mappings(self) -> _MappingResult:
        return self

    def one(self) -> dict[str, object]:
        return self._row


class _MessageConnection:
    def __init__(self, *, is_organizer: bool, is_viewer: bool) -> None:
        self.is_organizer = is_organizer
        self.is_viewer = is_viewer

    async def execute(self, *args: object, **kwargs: object) -> _MappingResult:
        return _MappingResult(
            {
                "body": "Добро пожаловать",
                "created_at": datetime(2026, 8, 10, 12, 0, tzinfo=UTC),
                "display_name": "Амина",
                "is_organizer": self.is_organizer,
                "is_viewer": self.is_viewer,
            }
        )


async def test_message_payload_marks_current_viewer() -> None:
    payload = await _message_payload(
        _MessageConnection(is_organizer=False, is_viewer=True),
        uuid.uuid4(),
        uuid.uuid4(),
        uuid.uuid4(),
    )
    assert payload["author_is_viewer"] is True
    assert payload["author_is_organizer"] is False


async def test_message_payload_keeps_organizer_and_viewer_roles_independent() -> None:
    payload = await _message_payload(
        _MessageConnection(is_organizer=True, is_viewer=False),
        uuid.uuid4(),
        uuid.uuid4(),
        uuid.uuid4(),
    )
    assert payload["author_is_viewer"] is False
    assert payload["author_is_organizer"] is True
