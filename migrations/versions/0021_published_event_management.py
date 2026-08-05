"""Add published event changes, cancellation facts and idempotency."""

from collections.abc import Sequence

from alembic import op

revision: str = "0021_published_event_management"
down_revision: str | None = "0020_event_moderation_publication"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE events.events ADD COLUMN cancellation_reason_code varchar(64)"
    )
    op.execute("ALTER TABLE events.events ADD COLUMN cancelled_at timestamptz")
    op.execute(
        "UPDATE events.events SET cancellation_reason_code='legacy_cancellation', "
        "cancelled_at=updated_at WHERE lifecycle_status='cancelled'"
    )
    op.execute(
        "ALTER TABLE events.events ADD CONSTRAINT events_cancellation_fact_check "
        "CHECK ((lifecycle_status = 'cancelled') = "
        "(cancellation_reason_code IS NOT NULL AND cancelled_at IS NOT NULL))"
    )
    op.execute(
        """
        CREATE TABLE events.change_requests (
            user_id uuid NOT NULL,
            idempotency_key uuid NOT NULL,
            request_fingerprint char(64) NOT NULL,
            event_id uuid NOT NULL,
            revision_id uuid NOT NULL UNIQUE,
            created_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (user_id, idempotency_key)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE events.change_requests")
    op.execute(
        "ALTER TABLE events.events DROP CONSTRAINT events_cancellation_fact_check"
    )
    op.execute("ALTER TABLE events.events DROP COLUMN cancelled_at")
    op.execute("ALTER TABLE events.events DROP COLUMN cancellation_reason_code")
