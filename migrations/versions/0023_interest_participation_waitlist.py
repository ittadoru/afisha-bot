"""Add event interests, automatic FIFO waitlist and participant exclusions."""

from collections.abc import Sequence

from alembic import op

revision: str = "0023_interest_participation_waitlist"
down_revision: str | None = "0022_public_event_discovery"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE events.event_interests (
            event_id uuid NOT NULL REFERENCES events.events(id) ON DELETE CASCADE,
            user_id uuid NOT NULL,
            active boolean NOT NULL DEFAULT true,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (event_id, user_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_events_interests_active "
        "ON events.event_interests(event_id) WHERE active"
    )
    op.execute(
        """
        CREATE TABLE events.waitlist_entries (
            id uuid PRIMARY KEY,
            event_id uuid NOT NULL REFERENCES events.events(id) ON DELETE CASCADE,
            user_id uuid NOT NULL,
            queue_order bigint GENERATED ALWAYS AS IDENTITY,
            status text NOT NULL DEFAULT 'waiting'
                CHECK (status IN ('waiting','promoted','left','cancelled')),
            queued_at timestamptz NOT NULL DEFAULT now(),
            closed_at timestamptz,
            CHECK ((status='waiting' AND closed_at IS NULL)
                OR (status<>'waiting' AND closed_at IS NOT NULL)),
            UNIQUE (queue_order)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_events_active_waitlist "
        "ON events.waitlist_entries(event_id,user_id) WHERE status='waiting'"
    )
    op.execute(
        "CREATE INDEX ix_events_waitlist_fifo "
        "ON events.waitlist_entries(event_id,queue_order) WHERE status='waiting'"
    )
    op.execute(
        "ALTER TABLE events.participation_episodes "
        "ADD COLUMN excluded_by_user_id uuid, "
        "ADD COLUMN close_note varchar(300)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE events.participation_episodes "
        "DROP COLUMN close_note, DROP COLUMN excluded_by_user_id"
    )
    op.execute("DROP TABLE events.waitlist_entries")
    op.execute("DROP TABLE events.event_interests")
