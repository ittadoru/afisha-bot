"""Enable the platform-owned PostGIS extension."""

from collections.abc import Sequence

from alembic import op

revision: str = "0001_platform_postgis"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")


def downgrade() -> None:
    # Platform extension removal is intentionally a forward-fix/restore decision.
    pass
