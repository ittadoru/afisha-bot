"""Keep organizer-confirmed address separate from the map result."""

from collections.abc import Sequence

from alembic import op

revision: str = "0027_event_organizer_address"
down_revision: str | None = "0026_looking_posts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE events.event_revisions "
        "ADD COLUMN organizer_address varchar(300)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE events.event_revisions DROP COLUMN organizer_address")
