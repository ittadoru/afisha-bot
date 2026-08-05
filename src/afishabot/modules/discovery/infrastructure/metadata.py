from sqlalchemy import Boolean, Column, DateTime, Integer, MetaData, SmallInteger, String, Table
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
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
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
