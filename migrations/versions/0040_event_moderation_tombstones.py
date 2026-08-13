"""Finalize hidden event moderation as privacy-preserving tombstones."""

from collections.abc import Sequence

from alembic import op

revision: str = "0040_event_moderation_tombstones"
down_revision: str | None = "0039_reversible_moderation_sanctions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE events.events ADD COLUMN moderation_deleted_at timestamptz")
    op.execute("ALTER TABLE trust_safety.moderation_sanctions DROP CONSTRAINT moderation_sanctions_status_check")
    op.execute("ALTER TABLE trust_safety.moderation_sanctions ADD CONSTRAINT moderation_sanctions_status_check CHECK (status IN ('active','reversed','restored','superseded','reversed_without_restore','finalized'))")
    op.execute("CREATE INDEX ix_events_moderation_deleted_at ON events.events(moderation_deleted_at) WHERE moderation_deleted_at IS NOT NULL")


def downgrade() -> None:
    op.execute("DROP INDEX events.ix_events_moderation_deleted_at")
    op.execute("ALTER TABLE trust_safety.moderation_sanctions DROP CONSTRAINT moderation_sanctions_status_check")
    op.execute("ALTER TABLE trust_safety.moderation_sanctions ADD CONSTRAINT moderation_sanctions_status_check CHECK (status IN ('active','reversed','restored','superseded','reversed_without_restore'))")
    op.execute("ALTER TABLE events.events DROP COLUMN moderation_deleted_at")
