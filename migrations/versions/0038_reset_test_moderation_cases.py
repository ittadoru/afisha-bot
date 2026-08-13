"""Remove the pre-release moderation test queue."""

from collections.abc import Sequence

from alembic import op

revision: str = "0038_reset_test_moderation_cases"
down_revision: str | None = "0037_expand_case_decisions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # These records belong to the pre-release moderation test queue. Children
    # are deleted first so the reset remains valid with all foreign keys on.
    op.execute("DELETE FROM trust_safety.profile_restrictions")
    op.execute("DELETE FROM trust_safety.profile_violations")
    op.execute("DELETE FROM trust_safety.case_decisions")
    op.execute("DELETE FROM trust_safety.appeals")
    op.execute("DELETE FROM trust_safety.case_timeline_entries")
    op.execute("DELETE FROM trust_safety.reports")
    op.execute("DELETE FROM trust_safety.moderation_cases")
    op.execute("DELETE FROM trust_safety.profile_reports")


def downgrade() -> None:
    # Deleted test reports cannot be reconstructed.
    pass
