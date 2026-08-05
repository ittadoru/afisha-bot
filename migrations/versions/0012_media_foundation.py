"""Create protected media asset metadata."""

# ruff: noqa: E501 -- SQL is kept readable and directly executable by PostgreSQL.

from collections.abc import Sequence

from alembic import op

revision: str = "0012_media_foundation"
down_revision: str | None = "0011_events_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def execute_sql(script: str) -> None:
    for statement in script.split(";"):
        if statement := statement.strip():
            op.execute(statement)


def upgrade() -> None:
    execute_sql(
        """
        CREATE TABLE media.assets (
            id uuid PRIMARY KEY,
            owner_user_id uuid NOT NULL,
            purpose text NOT NULL CHECK (purpose IN ('profile_avatar', 'event_photo')),
            state text NOT NULL DEFAULT 'pending'
                CHECK (state IN ('pending', 'processing', 'ready', 'rejected', 'deleted')),
            storage_key text NOT NULL UNIQUE,
            mime_type varchar(100),
            byte_size bigint CHECK (byte_size IS NULL OR byte_size > 0),
            width integer CHECK (width IS NULL OR width > 0),
            height integer CHECK (height IS NULL OR height > 0),
            checksum_sha256 char(64),
            delete_after timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_media_assets_owner_user_id ON media.assets(owner_user_id);
        CREATE INDEX ix_media_assets_delete_after ON media.assets(delete_after)
            WHERE delete_after IS NOT NULL AND state <> 'deleted';
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE media.assets")
