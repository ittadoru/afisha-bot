"""Allow a concise manual event location note."""

from collections.abc import Sequence

from alembic import op

revision: str = "0024_event_location_note"
down_revision: str | None = "0023_interest_participation_waitlist"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE events.event_revisions ALTER COLUMN landmark TYPE varchar(80)")


def downgrade() -> None:
    op.execute("ALTER TABLE events.event_revisions ALTER COLUMN landmark TYPE varchar(20)")
