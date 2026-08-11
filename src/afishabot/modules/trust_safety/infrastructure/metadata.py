from sqlalchemy import JSON, Column, DateTime, Integer, MetaData, String, Table, Text
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
    Column("subject_component", String(32)),
    Column("status", String(16), nullable=False),
    Column("priority", String(16), nullable=False),
    Column("version", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("resolved_at", DateTime(timezone=True)),
    Column("appeal_deadline", DateTime(timezone=True)),
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
    Column("evidence_snapshot", JSON),
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

case_decisions = Table(
    "case_decisions", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("case_id", UUID(as_uuid=True), nullable=False),
    Column("actor_staff_id", UUID(as_uuid=True), nullable=False),
    Column("decision_type", String(24), nullable=False),
    Column("subject_component", String(32)),
    Column("staff_note", String(1000), nullable=False),
    Column("idempotency_key", UUID(as_uuid=True), nullable=False, unique=True),
    Column("case_version", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

profile_violations = Table(
    "profile_violations", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("case_id", UUID(as_uuid=True), nullable=False, unique=True),
    Column("user_id", UUID(as_uuid=True), nullable=False),
    Column("direction", String(24), nullable=False),
    Column("status", String(16), nullable=False),
    Column("confirm_after", DateTime(timezone=True), nullable=False),
    Column("confirmed_at", DateTime(timezone=True)),
    Column("reversed_at", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

profile_restrictions = Table(
    "profile_restrictions", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("user_id", UUID(as_uuid=True), nullable=False),
    Column("direction", String(24), nullable=False),
    Column("source_violation_id", UUID(as_uuid=True), nullable=False, unique=True),
    Column("starts_at", DateTime(timezone=True), nullable=False),
    Column("ends_at", DateTime(timezone=True), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
