"""Add staff case decisions and profile moderation enforcement."""
# ruff: noqa: E501

from collections.abc import Sequence

from alembic import op

revision: str = "0034_staff_case_moderation"
down_revision: str | None = "0033_product_ui_data_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _execute_statements(sql: str) -> None:
    for statement in sql.split(";"):
        if statement.strip():
            op.execute(statement)


def upgrade() -> None:
    _execute_statements(
        """
        ALTER TABLE trust_safety.moderation_cases
          ADD COLUMN subject_component varchar(32),
          ADD COLUMN appeal_deadline timestamptz;

        ALTER TABLE trust_safety.reports
          ADD COLUMN evidence_snapshot jsonb;

        ALTER TABLE discovery.looking_post_questions
          ADD COLUMN answer_hidden_at timestamptz;

        CREATE TABLE trust_safety.case_decisions (
          id uuid PRIMARY KEY,
          case_id uuid NOT NULL REFERENCES trust_safety.moderation_cases(id),
          actor_staff_id uuid NOT NULL REFERENCES trust_safety.staff_accounts(id),
          decision_type varchar(24) NOT NULL
            CHECK (decision_type IN ('dismiss','hide_content','appeal_upheld','appeal_reversed')),
          subject_component varchar(32),
          staff_note varchar(1000) NOT NULL,
          idempotency_key uuid NOT NULL UNIQUE,
          case_version integer NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_case_decisions_case_created
          ON trust_safety.case_decisions(case_id,created_at,id);

        CREATE TABLE trust_safety.profile_violations (
          id uuid PRIMARY KEY,
          case_id uuid NOT NULL UNIQUE REFERENCES trust_safety.moderation_cases(id),
          user_id uuid NOT NULL,
          direction varchar(24) NOT NULL
            CHECK (direction IN ('profile_media','profile_text')),
          status varchar(16) NOT NULL DEFAULT 'pending'
            CHECK (status IN ('pending','confirmed','reversed')),
          confirm_after timestamptz NOT NULL,
          confirmed_at timestamptz,
          reversed_at timestamptz,
          created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_profile_violations_user_direction_created
          ON trust_safety.profile_violations(user_id,direction,created_at DESC);
        CREATE INDEX ix_profile_violations_pending
          ON trust_safety.profile_violations(confirm_after)
          WHERE status='pending';

        CREATE TABLE trust_safety.profile_restrictions (
          id uuid PRIMARY KEY,
          user_id uuid NOT NULL,
          direction varchar(24) NOT NULL
            CHECK (direction IN ('profile_media','profile_text')),
          source_violation_id uuid NOT NULL UNIQUE
            REFERENCES trust_safety.profile_violations(id),
          starts_at timestamptz NOT NULL,
          ends_at timestamptz NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          CHECK (ends_at > starts_at)
        );
        CREATE INDEX ix_profile_restrictions_active
          ON trust_safety.profile_restrictions(user_id,direction,ends_at DESC);

        CREATE INDEX ix_moderation_cases_queue
          ON trust_safety.moderation_cases(status,priority,created_at,id);
        CREATE INDEX ix_appeals_queue
          ON trust_safety.appeals(status,created_at,id);

        UPDATE trust_safety.moderation_cases c
        SET subject_component = CASE r.reason_code
          WHEN 'photo' THEN 'avatar'
          WHEN 'display_name' THEN 'display_name'
          WHEN 'bio' THEN 'bio'
          ELSE NULL END
        FROM trust_safety.reports r
        WHERE r.case_id=c.id AND c.subject_type='profile'
          AND c.subject_component IS NULL;
        """
    )


def downgrade() -> None:
    _execute_statements(
        """
        DROP INDEX trust_safety.ix_appeals_queue;
        DROP INDEX trust_safety.ix_moderation_cases_queue;
        DROP TABLE trust_safety.profile_restrictions;
        DROP TABLE trust_safety.profile_violations;
        DROP TABLE trust_safety.case_decisions;
        ALTER TABLE discovery.looking_post_questions DROP COLUMN answer_hidden_at;
        ALTER TABLE trust_safety.reports DROP COLUMN evidence_snapshot;
        ALTER TABLE trust_safety.moderation_cases
          DROP COLUMN appeal_deadline,
          DROP COLUMN subject_component;
        """
    )
