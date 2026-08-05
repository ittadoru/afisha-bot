"""Create events, immutable revisions, photos and participation."""

# ruff: noqa: E501 -- SQL is kept readable and directly executable by PostgreSQL.

from collections.abc import Sequence

from alembic import op

revision: str = "0011_events_foundation"
down_revision: str | None = "0010_discovery_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def execute_sql(script: str) -> None:
    for statement in script.split(";"):
        if statement := statement.strip():
            op.execute(statement)


def upgrade() -> None:
    execute_sql(
        """
        CREATE TABLE events.events (
            id uuid PRIMARY KEY,
            kind text NOT NULL DEFAULT 'regular' CHECK (kind IN ('regular', 'special')),
            creator_user_id uuid,
            audit_actor_id uuid NOT NULL,
            city_id uuid NOT NULL,
            category_id uuid NOT NULL,
            lifecycle_status text NOT NULL DEFAULT 'pending'
                CHECK (lifecycle_status IN ('pending', 'published', 'hidden', 'cancelled', 'finished')),
            moderation_status text NOT NULL DEFAULT 'pending'
                CHECK (moderation_status IN ('pending', 'approved', 'rejected', 'held')),
            capacity integer CHECK (capacity IS NULL OR capacity >= 3),
            current_revision_id uuid,
            approved_revision_id uuid,
            schedule_changes_used smallint NOT NULL DEFAULT 0
                CHECK (schedule_changes_used BETWEEN 0 AND 1),
            version integer NOT NULL DEFAULT 1 CHECK (version > 0),
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CHECK ((kind = 'regular' AND creator_user_id IS NOT NULL)
                OR (kind = 'special' AND creator_user_id IS NULL)),
            CHECK (kind = 'regular' OR capacity IS NULL)
        );
        CREATE INDEX ix_events_events_city_status
            ON events.events(city_id, lifecycle_status);
        CREATE INDEX ix_events_events_category_status
            ON events.events(category_id, lifecycle_status);

        CREATE TABLE events.event_revisions (
            id uuid PRIMARY KEY,
            event_id uuid NOT NULL REFERENCES events.events(id) ON DELETE CASCADE,
            revision_number integer NOT NULL CHECK (revision_number > 0),
            title varchar(60) NOT NULL CHECK (char_length(title) BETWEEN 1 AND 60),
            description varchar(1000) NOT NULL CHECK (char_length(description) BETWEEN 1 AND 1000),
            rules varchar(1000),
            landmark varchar(20),
            starts_at timestamptz NOT NULL,
            ends_at timestamptz NOT NULL,
            location geography(Point, 4326) NOT NULL,
            normalized_address text NOT NULL,
            street_name text NOT NULL,
            address_visibility text NOT NULL DEFAULT 'exact_public'
                CHECK (address_visibility IN ('street_only', 'exact_participants', 'exact_public')),
            moderation_status text NOT NULL DEFAULT 'pending'
                CHECK (moderation_status IN ('pending', 'approved', 'rejected')),
            submitted_at timestamptz NOT NULL DEFAULT now(),
            decided_at timestamptz,
            UNIQUE (event_id, revision_number),
            CHECK (ends_at > starts_at),
            CHECK (ends_at <= starts_at + interval '7 days')
        );
        CREATE INDEX ix_events_revisions_location
            ON events.event_revisions USING gist(location);
        CREATE UNIQUE INDEX uq_events_one_pending_revision
            ON events.event_revisions(event_id) WHERE moderation_status = 'pending';

        ALTER TABLE events.events ADD CONSTRAINT fk_events_current_revision
            FOREIGN KEY (current_revision_id) REFERENCES events.event_revisions(id);
        ALTER TABLE events.events ADD CONSTRAINT fk_events_approved_revision
            FOREIGN KEY (approved_revision_id) REFERENCES events.event_revisions(id);

        CREATE TABLE events.event_photos (
            id uuid PRIMARY KEY,
            event_id uuid NOT NULL REFERENCES events.events(id) ON DELETE CASCADE,
            revision_id uuid NOT NULL REFERENCES events.event_revisions(id) ON DELETE CASCADE,
            media_asset_id uuid NOT NULL,
            position smallint NOT NULL DEFAULT 1 CHECK (position > 0),
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (revision_id, position),
            UNIQUE (revision_id, media_asset_id)
        );

        CREATE TABLE events.participation_episodes (
            id uuid PRIMARY KEY,
            event_id uuid NOT NULL REFERENCES events.events(id) ON DELETE CASCADE,
            user_id uuid NOT NULL,
            status text NOT NULL DEFAULT 'active'
                CHECK (status IN ('active', 'left', 'excluded', 'cancelled')),
            joined_at timestamptz NOT NULL DEFAULT now(),
            closed_at timestamptz,
            close_reason text,
            CHECK ((status = 'active' AND closed_at IS NULL)
                OR (status <> 'active' AND closed_at IS NOT NULL))
        );
        CREATE UNIQUE INDEX uq_events_active_participation
            ON events.participation_episodes(event_id, user_id)
            WHERE status = 'active';
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE events.participation_episodes")
    op.execute("DROP TABLE events.event_photos")
    op.execute("ALTER TABLE events.events DROP CONSTRAINT fk_events_approved_revision")
    op.execute("ALTER TABLE events.events DROP CONSTRAINT fk_events_current_revision")
    op.execute("DROP TABLE events.event_revisions")
    op.execute("DROP TABLE events.events")
