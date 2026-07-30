"""Create the empty media owner schema."""

from collections.abc import Sequence

from alembic import op

revision: str = "0008_media_schema"
down_revision: str | None = "0007_reputation_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA media")


def downgrade() -> None:
    op.execute("DROP SCHEMA media")
