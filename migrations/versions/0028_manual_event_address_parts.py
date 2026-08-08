"""Store the organizer's street and place separately from the map result."""

from collections.abc import Sequence

from alembic import op

revision: str = "0028_manual_event_address_parts"
down_revision: str | None = "0027_event_organizer_address"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE events.event_revisions "
        "ADD COLUMN organizer_street varchar(160), "
        "ADD COLUMN organizer_place varchar(140)"
    )
    op.execute(
        "ALTER TABLE events.event_revisions DROP CONSTRAINT "
        "IF EXISTS event_revisions_hidden_anchor_check"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE events.event_revisions "
        "ADD CONSTRAINT event_revisions_hidden_anchor_check CHECK "
        "(address_visibility='exact_public' OR street_anchor_id IS NOT NULL) NOT VALID"
    )
    op.execute(
        "ALTER TABLE events.event_revisions "
        "DROP COLUMN organizer_place, DROP COLUMN organizer_street"
    )
