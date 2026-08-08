from sqlalchemy import Boolean, Column, DateTime, Integer, MetaData, SmallInteger, String, Table, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.types import UserDefinedType

metadata = MetaData(schema="discovery")


class Geography(UserDefinedType[str]):
    cache_ok = True

    def get_col_spec(self, **_kwargs: object) -> str:
        return "geography(MultiPolygon,4326)"


class PointGeography(UserDefinedType[str]):
    cache_ok = True

    def get_col_spec(self, **_kwargs: object) -> str:
        return "geography(Point,4326)"


cities = Table(
    "cities",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("slug", String(64), nullable=False, unique=True),
    Column("name", String(100), nullable=False),
    Column("timezone", String(64), nullable=False),
    Column("boundary", Geography()),
    Column("boundary_source", String(), nullable=False),
    Column("is_active", Boolean, nullable=False),
    Column("low_activity_cleanup_enabled", Boolean, nullable=False),
    Column("looking_posts_enabled", Boolean, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)
looking_posts = Table(
    "looking_posts", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("author_user_id", UUID(as_uuid=True), nullable=False),
    Column("city_id", UUID(as_uuid=True), nullable=False),
    Column("category_id", UUID(as_uuid=True), nullable=False),
    Column("title", String(30), nullable=False), Column("body", String(300), nullable=False),
    Column("status", Text, nullable=False), Column("version", Integer, nullable=False),
    Column("pending_event_id", UUID(as_uuid=True)), Column("converted_event_id", UUID(as_uuid=True)),
    Column("created_at", DateTime(timezone=True), nullable=False), Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("closed_at", DateTime(timezone=True)), Column("delete_after", DateTime(timezone=True)),
)
looking_post_likes = Table(
    "looking_post_likes",
    metadata,
    Column("looking_post_id", UUID(as_uuid=True), primary_key=True),
    Column("user_id", UUID(as_uuid=True), primary_key=True),
    Column("active", Boolean, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)
looking_post_questions = Table(
    "looking_post_questions",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("looking_post_id", UUID(as_uuid=True), nullable=False),
    Column("asker_user_id", UUID(as_uuid=True), nullable=False),
    Column("question", String(200), nullable=False),
    Column("answer", String(300)),
    Column("answered_at", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("delete_after", DateTime(timezone=True)),
)
categories = Table(
    "categories",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("slug", String(64), nullable=False, unique=True),
    Column("name", String(64), nullable=False, unique=True),
    Column("sort_order", SmallInteger, nullable=False, unique=True),
    Column("is_special", Boolean, nullable=False),
    Column("organizer_selectable", Boolean, nullable=False),
    Column("is_active", Boolean, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
street_anchors = Table(
    "street_anchors",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("city_id", UUID(as_uuid=True), nullable=False),
    Column("street_key", String(200), nullable=False),
    Column("display_name", String(200), nullable=False),
    Column("provider_place_id", String(100), nullable=False),
    Column("anchor", PointGeography(), nullable=False),
    Column("geometry_version", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)
