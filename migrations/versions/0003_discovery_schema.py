"""Create the empty discovery owner schema."""

from collections.abc import Sequence

from alembic import op

revision: str = "0003_discovery_schema"
down_revision: str | None = "0002_accounts_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA discovery")


def downgrade() -> None:
    op.execute("DROP SCHEMA discovery")
