from sqlalchemy import (
    BigInteger,
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
