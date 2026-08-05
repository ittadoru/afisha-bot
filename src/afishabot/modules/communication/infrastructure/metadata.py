from sqlalchemy import Column, DateTime, MetaData, String, Table, Text
from sqlalchemy.dialects.postgresql import UUID

metadata = MetaData(schema="communication")

messages = Table(
    "messages",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("event_id", UUID(as_uuid=True), nullable=False),
    Column("author_user_id", UUID(as_uuid=True), nullable=False),
    Column("participation_episode_id", UUID(as_uuid=True), nullable=False),
    Column("body", String(500), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("delete_after", DateTime(timezone=True), nullable=False),
)
notifications = Table(
    "notifications",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("recipient_user_id", UUID(as_uuid=True), nullable=False),
    Column("kind", String(100), nullable=False),
    Column("importance", Text, nullable=False),
    Column("title", String(120), nullable=False),
    Column("body", String(500), nullable=False),
    Column("subject_type", String(64)),
    Column("subject_id", UUID(as_uuid=True)),
    Column("deep_link", Text),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("read_at", DateTime(timezone=True)),
    Column("expires_at", DateTime(timezone=True)),
)
