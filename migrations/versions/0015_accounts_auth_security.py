"""Add CSRF binding to Mini App sessions."""

from collections.abc import Sequence

from alembic import op

revision: str = "0015_accounts_auth_security"
down_revision: str | None = "0014_communication_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Earlier stages had no working user login, so any placeholder sessions are
    # unusable and can be safely removed before making CSRF binding mandatory.
    op.execute("DELETE FROM accounts.sessions")
    op.execute("ALTER TABLE accounts.sessions ADD COLUMN csrf_token_hash bytea")
    op.execute(
        "ALTER TABLE accounts.sessions ALTER COLUMN csrf_token_hash SET NOT NULL"
    )
    op.execute(
        """
        CREATE TABLE accounts.age_acceptances (
            id uuid PRIMARY KEY,
            user_id uuid NOT NULL REFERENCES accounts.users(id) ON DELETE CASCADE,
            rule_version text NOT NULL,
            accepted_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (user_id, rule_version)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE accounts.age_acceptances")
    op.execute("ALTER TABLE accounts.sessions DROP COLUMN csrf_token_hash")
