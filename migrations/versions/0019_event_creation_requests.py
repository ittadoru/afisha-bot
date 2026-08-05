"""Add idempotency records for complete event submission."""

from collections.abc import Sequence

from alembic import op

revision: str = "0019_event_creation_requests"
down_revision: str | None = "0018_staff_admin_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE events.creation_requests (
            user_id uuid NOT NULL,
            idempotency_key uuid NOT NULL,
            request_fingerprint char(64) NOT NULL,
            event_id uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (user_id, idempotency_key),
            UNIQUE (event_id)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE events.creation_requests")
