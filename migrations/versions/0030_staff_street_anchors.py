"""Allow moderators to maintain approximate street anchors."""

from collections.abc import Sequence

from alembic import op

revision: str = "0030_staff_street_anchors"
down_revision: str | None = "0029_event_chat_and_telegram"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE discovery.street_anchors ALTER COLUMN provider_place_id DROP NOT NULL")
    op.execute("ALTER TABLE discovery.street_anchors ADD COLUMN source varchar(16) NOT NULL DEFAULT 'nominatim' CHECK (source IN ('nominatim','staff'))")


def downgrade() -> None:
    op.execute("ALTER TABLE discovery.street_anchors DROP COLUMN source")
    op.execute("ALTER TABLE discovery.street_anchors ALTER COLUMN provider_place_id SET NOT NULL")
