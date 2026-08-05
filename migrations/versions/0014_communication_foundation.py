"""Create event messages and persistent notifications."""

from collections.abc import Sequence

from alembic import op

revision: str = "0014_communication_foundation"
down_revision: str | None = "0013_event_moderation_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE communication.messages (
            id uuid PRIMARY KEY,
            event_id uuid NOT NULL,
            author_user_id uuid NOT NULL,
            participation_episode_id uuid NOT NULL,
            body varchar(500) NOT NULL CHECK (char_length(body) BETWEEN 1 AND 500),
            created_at timestamptz NOT NULL DEFAULT now(),
            delete_after timestamptz NOT NULL
        );
        CREATE INDEX ix_communication_messages_event_created
            ON communication.messages(event_id, created_at, id);
        CREATE INDEX ix_communication_messages_delete_after
            ON communication.messages(delete_after);

        CREATE TABLE communication.notifications (
            id uuid PRIMARY KEY,
            recipient_user_id uuid NOT NULL,
            kind varchar(100) NOT NULL,
            importance text NOT NULL DEFAULT 'normal'
                CHECK (importance IN ('normal', 'critical')),
            title varchar(120) NOT NULL,
            body varchar(500) NOT NULL,
            subject_type varchar(64),
            subject_id uuid,
            deep_link text,
            created_at timestamptz NOT NULL DEFAULT now(),
            read_at timestamptz,
            expires_at timestamptz,
            CHECK ((subject_type IS NULL) = (subject_id IS NULL)),
            CHECK (expires_at IS NULL OR expires_at > created_at),
            CHECK (read_at IS NULL OR read_at >= created_at)
        );
        CREATE INDEX ix_communication_notifications_unread
            ON communication.notifications(recipient_user_id, created_at DESC)
            WHERE read_at IS NULL;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE communication.notifications")
    op.execute("DROP TABLE communication.messages")
