import uuid

from asyncpg.pgproto.pgproto import UUID as PgUUID

from afishabot.modules.communication.application.event_chat import _active_episode


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
