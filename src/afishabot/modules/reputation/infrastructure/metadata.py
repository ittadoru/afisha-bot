from sqlalchemy import Column, DateTime, Integer, MetaData, Table, Text
from sqlalchemy.dialects.postgresql import UUID

metadata = MetaData(schema="reputation")

organizer_profiles = Table(
    "organizer_profiles", metadata,
    Column("user_id", UUID(as_uuid=True), primary_key=True),
    Column("status", Text, nullable=False),
    Column("successful_events", Integer, nullable=False),
    Column("version", Integer, nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)
