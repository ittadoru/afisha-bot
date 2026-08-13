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
    Column("hidden_at", DateTime(timezone=True)),
    Column("hidden_by_case_id", UUID(as_uuid=True)),
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
    Column("tg_pushed_at", DateTime(timezone=True)),
    Column("business_key", String(180)),
    Column("delivery_policy", Text, nullable=False),
    Column("telegram_status", Text, nullable=False),
    Column("telegram_last_attempt_at", DateTime(timezone=True)),
    Column("telegram_sent_at", DateTime(timezone=True)),
)

chat_message_requests = Table(
    "chat_message_requests",
    metadata,
    Column("user_id", UUID(as_uuid=True), primary_key=True),
    Column("idempotency_key", UUID(as_uuid=True), primary_key=True),
    Column("request_fingerprint", String(64), nullable=False),
    Column("message_id", UUID(as_uuid=True), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
