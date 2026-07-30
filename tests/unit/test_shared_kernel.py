from datetime import UTC, datetime
from uuid import uuid4

from afishabot.shared_kernel.errors import ApplicationError
from afishabot.shared_kernel.events import EventEnvelope
from afishabot.shared_kernel.ids import EntityId


def test_event_envelope_and_typed_id_are_technical_only() -> None:
    aggregate_id = uuid4()
    envelope = EventEnvelope(
        event_id=uuid4(),
        event_type="platform.test",
        schema_version=1,
        occurred_at=datetime.now(UTC),
        aggregate_id=aggregate_id,
        correlation_id=uuid4(),
    )

    assert envelope.aggregate_id == EntityId(aggregate_id)
    assert issubclass(ApplicationError, Exception)
