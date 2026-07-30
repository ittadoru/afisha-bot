"""Create the empty trust_safety owner schema."""

from collections.abc import Sequence

from alembic import op

revision: str = "0006_trust_safety_schema"
down_revision: str | None = "0005_communication_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA trust_safety")


def downgrade() -> None:
    op.execute("DROP SCHEMA trust_safety")
