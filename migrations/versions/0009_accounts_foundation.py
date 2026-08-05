"""Create the accounts data foundation."""

# ruff: noqa: E501 -- SQL is kept readable and directly executable by PostgreSQL.

from collections.abc import Sequence

from alembic import op

revision: str = "0009_accounts_foundation"
down_revision: str | None = "0008_media_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def execute_sql(script: str) -> None:
    for statement in script.split(";"):
        if statement := statement.strip():
            op.execute(statement)


def upgrade() -> None:
    execute_sql(
        """
        CREATE TABLE accounts.users (
            id uuid PRIMARY KEY,
            status text NOT NULL DEFAULT 'active'
                CHECK (status IN ('active', 'restricted', 'blocked', 'deleted')),
            accepted_age_rule_version text,
            accepted_age_rule_at timestamptz,
            version integer NOT NULL DEFAULT 1 CHECK (version > 0),
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CHECK ((accepted_age_rule_version IS NULL) = (accepted_age_rule_at IS NULL))
        );

        CREATE TABLE accounts.telegram_identities (
            user_id uuid PRIMARY KEY REFERENCES accounts.users(id) ON DELETE CASCADE,
            telegram_user_id bigint NOT NULL UNIQUE CHECK (telegram_user_id > 0),
            first_authenticated_at timestamptz NOT NULL DEFAULT now(),
            last_authenticated_at timestamptz NOT NULL DEFAULT now()
        );

        CREATE TABLE accounts.profiles (
            user_id uuid PRIMARY KEY REFERENCES accounts.users(id) ON DELETE CASCADE,
            public_id char(8) NOT NULL UNIQUE,
            display_name varchar(32) NOT NULL CHECK (char_length(display_name) BETWEEN 3 AND 32),
            bio varchar(150),
            selected_city_id uuid,
            avatar_asset_id uuid,
            display_name_changed_at timestamptz,
            version integer NOT NULL DEFAULT 1 CHECK (version > 0),
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        );

        CREATE TABLE accounts.sessions (
            id uuid PRIMARY KEY,
            user_id uuid NOT NULL REFERENCES accounts.users(id) ON DELETE CASCADE,
            token_hash bytea NOT NULL UNIQUE,
            expires_at timestamptz NOT NULL,
            revoked_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            CHECK (expires_at > created_at)
        );
        CREATE INDEX ix_accounts_sessions_user_id ON accounts.sessions(user_id);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE accounts.sessions")
    op.execute("DROP TABLE accounts.profiles")
    op.execute("DROP TABLE accounts.telegram_identities")
    op.execute("DROP TABLE accounts.users")
