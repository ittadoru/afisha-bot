"""Keep moderation actions reversible throughout the appeal window."""

from collections.abc import Sequence

from alembic import op

revision: str = "0039_reversible_moderation_sanctions"
down_revision: str | None = "0038_reset_test_moderation_cases"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE media.assets DROP CONSTRAINT assets_state_check"
    )
    op.execute(
        "ALTER TABLE media.assets ADD CONSTRAINT assets_state_check "
        "CHECK (state IN ('pending','processing','ready','rejected','deleted','moderation_hidden'))"
    )
    op.execute(
        "ALTER TABLE discovery.looking_post_questions "
        "ADD COLUMN answer_hidden_by_case_id uuid"
    )
    op.execute("""
      CREATE TABLE trust_safety.moderation_sanctions (
        id uuid PRIMARY KEY,
        case_id uuid NOT NULL UNIQUE REFERENCES trust_safety.moderation_cases(id),
        decision_type varchar(24) NOT NULL,
        subject_component varchar(32),
        subject_version_before integer NOT NULL,
        subject_version_after integer NOT NULL,
        previous_state jsonb NOT NULL,
        status varchar(24) NOT NULL DEFAULT 'active'
          CHECK (status IN ('active','reversed','restored','superseded','reversed_without_restore')),
        created_at timestamptz NOT NULL DEFAULT now(),
        reversed_at timestamptz
      )
    """)
    op.execute(
        "CREATE INDEX ix_moderation_sanctions_active "
        "ON trust_safety.moderation_sanctions(status,created_at)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX trust_safety.ix_moderation_sanctions_active")
    op.execute("DROP TABLE trust_safety.moderation_sanctions")
    op.execute(
        "ALTER TABLE discovery.looking_post_questions DROP COLUMN answer_hidden_by_case_id"
    )
    op.execute("ALTER TABLE media.assets DROP CONSTRAINT assets_state_check")
    op.execute(
        "ALTER TABLE media.assets ADD CONSTRAINT assets_state_check "
        "CHECK (state IN ('pending','processing','ready','rejected','deleted'))"
    )
