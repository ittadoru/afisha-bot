"""Expand moderation case decision types."""

from collections.abc import Sequence

from alembic import op

revision: str = "0037_expand_case_decisions"
down_revision: str | None = "0036_typed_moderation_evidence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE trust_safety.case_decisions "
        "DROP CONSTRAINT case_decisions_decision_type_check"
    )
    op.execute(
        "ALTER TABLE trust_safety.case_decisions "
        "ADD CONSTRAINT case_decisions_decision_type_check "
        "CHECK (decision_type IN ("
        "'dismiss','hide_content','hide_component','hold_for_correction',"
        "'hide_subject','appeal_upheld','appeal_reversed'))"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE trust_safety.case_decisions SET decision_type='hide_content' "
        "WHERE decision_type IN ('hide_component','hold_for_correction','hide_subject')"
    )
    op.execute(
        "ALTER TABLE trust_safety.case_decisions "
        "DROP CONSTRAINT case_decisions_decision_type_check"
    )
    op.execute(
        "ALTER TABLE trust_safety.case_decisions "
        "ADD CONSTRAINT case_decisions_decision_type_check "
        "CHECK (decision_type IN ("
        "'dismiss','hide_content','appeal_upheld','appeal_reversed'))"
    )
