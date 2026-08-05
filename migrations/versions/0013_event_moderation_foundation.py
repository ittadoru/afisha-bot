"""Create the event moderation review foundation."""

from collections.abc import Sequence

from alembic import op

revision: str = "0013_event_moderation_foundation"
down_revision: str | None = "0012_media_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def execute_sql(script: str) -> None:
    for statement in script.split(";"):
        if statement := statement.strip():
            op.execute(statement)


def upgrade() -> None:
    execute_sql(
        """
        CREATE TABLE trust_safety.event_reviews (
            id uuid PRIMARY KEY,
            event_id uuid NOT NULL,
            event_revision_id uuid NOT NULL UNIQUE,
            status text NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'approved', 'rejected', 'held')),
            priority text NOT NULL DEFAULT 'normal'
                CHECK (priority IN ('low', 'normal', 'high', 'emergency')),
            submitted_by_user_id uuid NOT NULL,
            decided_by_staff_id uuid,
            normalized_reason_code varchar(100),
            submitted_at timestamptz NOT NULL DEFAULT now(),
            decided_at timestamptz,
            CHECK ((status = 'pending' AND decided_at IS NULL)
                OR (status <> 'pending' AND decided_at IS NOT NULL)),
            CHECK (decided_at IS NULL OR decided_at >= submitted_at)
        );
        CREATE INDEX ix_trust_safety_event_reviews_queue
            ON trust_safety.event_reviews(status, priority, submitted_at);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE trust_safety.event_reviews")
