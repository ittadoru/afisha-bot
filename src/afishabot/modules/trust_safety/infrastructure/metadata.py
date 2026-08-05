from sqlalchemy import Column, DateTime, MetaData, String, Table, Text
from sqlalchemy.dialects.postgresql import UUID

metadata = MetaData(schema="trust_safety")

event_reviews = Table(
    "event_reviews",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("event_id", UUID(as_uuid=True), nullable=False),
    Column("event_revision_id", UUID(as_uuid=True), nullable=False, unique=True),
    Column("status", Text, nullable=False),
    Column("priority", Text, nullable=False),
    Column("submitted_by_user_id", UUID(as_uuid=True), nullable=False),
    Column("decided_by_staff_id", UUID(as_uuid=True)),
    Column("normalized_reason_code", String(100)),
    Column("submitted_at", DateTime(timezone=True), nullable=False),
    Column("decided_at", DateTime(timezone=True)),
)
profile_reports = Table(
    "profile_reports", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("reporter_user_id", UUID(as_uuid=True), nullable=False),
    Column("subject_user_id", UUID(as_uuid=True), nullable=False),
    Column("reason", Text, nullable=False),
    Column("comment", String(300)),
    Column("avatar_asset_id", UUID(as_uuid=True)),
    Column("status", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("decided_at", DateTime(timezone=True)),
)
