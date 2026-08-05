"""Add moderation resubmission and staff-owned special event support."""

from collections.abc import Sequence

from alembic import op

revision: str = "0020_event_moderation_publication"
down_revision: str | None = "0019_event_creation_requests"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE events.events DROP CONSTRAINT events_lifecycle_status_check")
    op.execute(
        "ALTER TABLE events.events ADD CONSTRAINT events_lifecycle_status_check "
        "CHECK (lifecycle_status IN "
        "('pending','published','rejected','hidden','cancelled','finished'))"
    )
    op.execute(
        "ALTER TABLE events.events ADD COLUMN resubmissions_used smallint "
        "NOT NULL DEFAULT 0 CHECK (resubmissions_used BETWEEN 0 AND 3)"
    )
    op.execute("ALTER TABLE media.assets ALTER COLUMN owner_user_id DROP NOT NULL")
    op.execute("ALTER TABLE media.assets ADD COLUMN owner_staff_id uuid")
    op.execute(
        "ALTER TABLE media.assets ADD CONSTRAINT media_assets_exactly_one_owner "
        "CHECK ((owner_user_id IS NOT NULL)::integer + "
        "(owner_staff_id IS NOT NULL)::integer = 1)"
    )
    op.execute(
        """
        CREATE TABLE events.staff_creation_requests (
            staff_id uuid NOT NULL,
            idempotency_key uuid NOT NULL,
            request_fingerprint char(64) NOT NULL,
            event_id uuid NOT NULL UNIQUE,
            created_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (staff_id, idempotency_key)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE events.staff_creation_requests")
    op.execute("ALTER TABLE media.assets DROP CONSTRAINT media_assets_exactly_one_owner")
    op.execute("ALTER TABLE media.assets DROP COLUMN owner_staff_id")
    op.execute("ALTER TABLE media.assets ALTER COLUMN owner_user_id SET NOT NULL")
    op.execute("ALTER TABLE events.events DROP COLUMN resubmissions_used")
    op.execute("ALTER TABLE events.events DROP CONSTRAINT events_lifecycle_status_check")
    op.execute(
        "ALTER TABLE events.events ADD CONSTRAINT events_lifecycle_status_check "
        "CHECK (lifecycle_status IN "
        "('pending','published','hidden','cancelled','finished'))"
    )
