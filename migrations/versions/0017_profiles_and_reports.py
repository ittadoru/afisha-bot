"""Add organizer profile projection and profile reports."""

from collections.abc import Sequence

from alembic import op

revision: str = "0017_profiles_and_reports"
down_revision: str | None = "0016_discovery_boundaries"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE reputation.organizer_profiles (
            user_id uuid PRIMARY KEY,
            status text NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'trusted')),
            successful_events integer NOT NULL DEFAULT 0 CHECK (successful_events >= 0),
            version integer NOT NULL DEFAULT 1 CHECK (version > 0),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CHECK (status <> 'trusted' OR successful_events >= 3)
        );
        INSERT INTO reputation.organizer_profiles (user_id)
        SELECT id FROM accounts.users;

        CREATE TABLE trust_safety.profile_reports (
            id uuid PRIMARY KEY,
            reporter_user_id uuid NOT NULL,
            subject_user_id uuid NOT NULL,
            reason text NOT NULL CHECK (reason IN ('photo', 'display_name', 'bio', 'other')),
            comment varchar(300),
            avatar_asset_id uuid,
            status text NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'reviewed', 'dismissed', 'actioned')),
            created_at timestamptz NOT NULL DEFAULT now(),
            decided_at timestamptz,
            CHECK (reporter_user_id <> subject_user_id),
            CHECK (reason <> 'other' OR char_length(trim(comment)) > 0)
        );
        CREATE UNIQUE INDEX uq_profile_reports_open_reason
            ON trust_safety.profile_reports(reporter_user_id, subject_user_id, reason)
            WHERE status IN ('pending', 'reviewed');
        CREATE INDEX ix_profile_reports_queue
            ON trust_safety.profile_reports(status, created_at);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE trust_safety.profile_reports")
    op.execute("DROP TABLE reputation.organizer_profiles")
