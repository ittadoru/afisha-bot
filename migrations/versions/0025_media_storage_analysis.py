"""Persist the latest low-cost admin media analysis."""

from collections.abc import Sequence

from alembic import op

revision: str = "0025_media_storage_analysis"
down_revision: str | None = "0024_event_location_note"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE media.storage_analysis (
            id integer PRIMARY KEY CHECK (id = 1),
            inventory_collected_at timestamptz,
            inventory text,
            estimate_status varchar(16) NOT NULL DEFAULT 'idle'
                CHECK (estimate_status IN ('idle','queued','running','completed','failed')),
            estimate_job_id uuid,
            estimate_collected_at timestamptz,
            estimate text,
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE media.storage_analysis")
