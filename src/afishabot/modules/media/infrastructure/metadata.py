from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID

metadata = MetaData(schema="media")

assets = Table(
    "assets",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("owner_user_id", UUID(as_uuid=True), nullable=False),
    Column("purpose", Text, nullable=False),
    Column("state", Text, nullable=False),
    Column("storage_key", Text, nullable=False, unique=True),
    Column("mime_type", String(100)),
    Column("byte_size", BigInteger),
    Column("width", Integer),
    Column("height", Integer),
    Column("checksum_sha256", String(64)),
    Column("delete_after", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

asset_variants = Table(
    "asset_variants",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("source_asset_id", UUID(as_uuid=True), nullable=False),
    Column("variant_key", String(40), nullable=False),
    Column("storage_key", Text, nullable=False, unique=True),
    Column("mime_type", String(100), nullable=False),
    Column("width", Integer, nullable=False),
    Column("height", Integer, nullable=False),
    Column("byte_size", BigInteger, nullable=False),
    Column("checksum_sha256", String(64), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

storage_analysis = Table(
    "storage_analysis",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("inventory_collected_at", DateTime(timezone=True)),
    Column("inventory", Text),
    Column("estimate_status", String(16), nullable=False, server_default="idle"),
    Column("estimate_job_id", UUID(as_uuid=True)),
    Column("estimate_collected_at", DateTime(timezone=True)),
    Column("estimate", Text),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("id = 1", name="media_storage_analysis_singleton"),
    CheckConstraint(
        "estimate_status IN ('idle', 'queued', 'running', 'completed', 'failed')",
        name="media_storage_analysis_estimate_status",
    ),
)
