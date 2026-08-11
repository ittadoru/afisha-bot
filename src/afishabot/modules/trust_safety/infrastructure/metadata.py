from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, Text
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
    Column("background_asset_id", UUID(as_uuid=True)),
    Column("status", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("decided_at", DateTime(timezone=True)),
)

moderation_cases = Table(
    "moderation_cases", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("public_id", String(11), nullable=False, unique=True),
    Column("subject_type", String(32), nullable=False),
    Column("subject_id", UUID(as_uuid=True), nullable=False),
    Column("subject_owner_user_id", UUID(as_uuid=True)),
    Column("status", String(16), nullable=False),
    Column("priority", String(16), nullable=False),
    Column("version", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("resolved_at", DateTime(timezone=True)),
)

reports = Table(
    "reports", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("case_id", UUID(as_uuid=True), nullable=False),
    Column("reporter_user_id", UUID(as_uuid=True), nullable=False),
    Column("reason_code", String(64), nullable=False),
    Column("explanation", String(500)),
    Column("idempotency_key", UUID(as_uuid=True), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

case_timeline_entries = Table(
    "case_timeline_entries", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("case_id", UUID(as_uuid=True), nullable=False),
    Column("event_type", String(32), nullable=False),
    Column("public_label", String(160), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

appeals = Table(
    "appeals", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("case_id", UUID(as_uuid=True), nullable=False),
    Column("appellant_user_id", UUID(as_uuid=True), nullable=False),
    Column("explanation", String(500), nullable=False),
    Column("status", String(16), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("decided_at", DateTime(timezone=True)),
)
