"""Create the empty accounts owner schema."""

from collections.abc import Sequence

from alembic import op

revision: str = "0002_accounts_schema"
down_revision: str | None = "0001_platform_postgis"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA accounts")


def downgrade() -> None:
    op.execute("DROP SCHEMA accounts")
