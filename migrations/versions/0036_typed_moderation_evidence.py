"""Add typed report evidence and reset pre-contract test cases."""

from collections.abc import Sequence

from alembic import op

revision: str = "0036_typed_moderation_evidence"
down_revision: str | None = "0035_unify_categories_and_map_markers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Existing rows were produced by the prototype contract and are test data.
    # The order is intentional: children are removed before moderation cases.
    op.execute("DELETE FROM trust_safety.profile_restrictions")
    op.execute("DELETE FROM trust_safety.profile_violations")
    op.execute("DELETE FROM trust_safety.case_decisions")
    op.execute("DELETE FROM trust_safety.appeals")
    op.execute("DELETE FROM trust_safety.case_timeline_entries")
    op.execute("DELETE FROM trust_safety.reports")
    op.execute("DELETE FROM trust_safety.moderation_cases")
    op.execute("DELETE FROM trust_safety.profile_reports")
    op.execute(
        "ALTER TABLE communication.messages ADD COLUMN hidden_at timestamptz"
    )
    op.execute(
        "ALTER TABLE communication.messages ADD COLUMN hidden_by_case_id uuid"
    )
    op.execute(
        "CREATE INDEX ix_communication_messages_visible "
        "ON communication.messages(event_id,created_at,id) WHERE hidden_at IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX communication.ix_communication_messages_visible")
    op.execute(
        "ALTER TABLE communication.messages DROP COLUMN hidden_by_case_id, "
        "DROP COLUMN hidden_at"
    )
