from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    SmallInteger,
    String,
    Table,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.types import UserDefinedType

metadata = MetaData(schema="events")


class Geography(UserDefinedType[str]):
    cache_ok = True

    def get_col_spec(self, **_kwargs: object) -> str:
        return "geography(Point,4326)"


events = Table(
    "events",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("kind", Text, nullable=False),
    Column("creator_user_id", UUID(as_uuid=True)),
    Column("audit_actor_id", UUID(as_uuid=True), nullable=False),
    Column("city_id", UUID(as_uuid=True), nullable=False),
    Column("category_id", UUID(as_uuid=True), nullable=False),
    Column("lifecycle_status", Text, nullable=False),
    Column("moderation_status", Text, nullable=False),
    Column("capacity", Integer),
    Column(
        "current_revision_id",
        ForeignKey(
            "events.event_revisions.id",
            name="fk_events_current_revision",
            use_alter=True,
        ),
    ),
    Column(
        "approved_revision_id",
        ForeignKey(
            "events.event_revisions.id",
            name="fk_events_approved_revision",
            use_alter=True,
        ),
    ),
    Column("schedule_changes_used", SmallInteger, nullable=False),
    Column("version", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)
event_revisions = Table(
    "event_revisions",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("event_id", ForeignKey("events.events.id"), nullable=False),
    Column("revision_number", Integer, nullable=False),
    Column("title", String(60), nullable=False),
    Column("description", String(1000), nullable=False),
    Column("rules", String(1000)),
    Column("landmark", String(20)),
    Column("starts_at", DateTime(timezone=True), nullable=False),
    Column("ends_at", DateTime(timezone=True), nullable=False),
    Column("location", Geography(), nullable=False),
    Column("normalized_address", Text, nullable=False),
    Column("street_name", Text, nullable=False),
    Column("address_visibility", Text, nullable=False),
    Column("moderation_status", Text, nullable=False),
    Column("submitted_at", DateTime(timezone=True), nullable=False),
    Column("decided_at", DateTime(timezone=True)),
)
event_photos = Table(
    "event_photos",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("event_id", ForeignKey("events.events.id"), nullable=False),
    Column("revision_id", ForeignKey("events.event_revisions.id"), nullable=False),
    Column("media_asset_id", UUID(as_uuid=True), nullable=False),
    Column("position", SmallInteger, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
participation_episodes = Table(
    "participation_episodes",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("event_id", ForeignKey("events.events.id"), nullable=False),
    Column("user_id", UUID(as_uuid=True), nullable=False),
    Column("status", Text, nullable=False),
    Column("joined_at", DateTime(timezone=True), nullable=False),
    Column("closed_at", DateTime(timezone=True)),
    Column("close_reason", Text),
)
