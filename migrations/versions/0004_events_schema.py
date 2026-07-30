"""Create the empty events owner schema."""

from collections.abc import Sequence

from alembic import op

revision: str = "0004_events_schema"
down_revision: str | None = "0003_discovery_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA events")


def downgrade() -> None:
    op.execute("DROP SCHEMA events")
