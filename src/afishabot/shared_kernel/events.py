from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class EventEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_id: UUID
    event_type: str
    schema_version: int
    occurred_at: datetime
    aggregate_id: UUID
    correlation_id: UUID
