from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Table,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID

metadata = MetaData(schema="accounts")

users = Table(
    "users",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("status", Text, nullable=False),
    Column("accepted_age_rule_version", Text),
    Column("accepted_age_rule_at", DateTime(timezone=True)),
    Column("version", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)
telegram_identities = Table(
    "telegram_identities",
    metadata,
    Column(
        "user_id",
        UUID(as_uuid=True),
        ForeignKey("accounts.users.id"),
        primary_key=True,
    ),
    Column("telegram_user_id", BigInteger, nullable=False, unique=True),
    Column("first_authenticated_at", DateTime(timezone=True), nullable=False),
    Column("last_authenticated_at", DateTime(timezone=True), nullable=False),
)
profiles = Table(
    "profiles",
    metadata,
    Column(
        "user_id",
        UUID(as_uuid=True),
        ForeignKey("accounts.users.id"),
        primary_key=True,
    ),
    Column("public_id", String(8), nullable=False, unique=True),
    Column("display_name", String(32), nullable=False),
    Column("bio", String(150)),
    Column("selected_city_id", UUID(as_uuid=True)),
    Column("avatar_asset_id", UUID(as_uuid=True)),
    Column("display_name_changed_at", DateTime(timezone=True)),
    Column("version", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)
sessions = Table(
    "sessions",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column(
        "user_id",
        UUID(as_uuid=True),
        ForeignKey("accounts.users.id"),
        nullable=False,
    ),
    Column("token_hash", LargeBinary, nullable=False, unique=True),
    Column("csrf_token_hash", LargeBinary, nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("revoked_at", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
age_acceptances = Table(
    "age_acceptances",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column(
        "user_id",
        UUID(as_uuid=True),
        ForeignKey("accounts.users.id"),
        nullable=False,
    ),
    Column("rule_version", Text, nullable=False),
    Column("accepted_at", DateTime(timezone=True), nullable=False),
)
