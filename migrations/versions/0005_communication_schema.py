"""Create the empty communication owner schema."""

from collections.abc import Sequence

from alembic import op

revision: str = "0005_communication_schema"
down_revision: str | None = "0004_events_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA communication")


def downgrade() -> None:
    op.execute("DROP SCHEMA communication")
