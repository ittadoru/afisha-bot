"""Add LookingPost feed, questions and conversion state."""

from collections.abc import Sequence

from alembic import op

revision: str = "0026_looking_posts"
down_revision: str | None = "0025_media_storage_analysis"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE discovery.cities ADD COLUMN looking_posts_enabled boolean NOT NULL DEFAULT true"
    )
    op.execute(
        """
        CREATE TABLE discovery.looking_posts (
            id uuid PRIMARY KEY,
            author_user_id uuid NOT NULL,
            city_id uuid NOT NULL REFERENCES discovery.cities(id),
            category_id uuid NOT NULL REFERENCES discovery.categories(id),
            title varchar(30) NOT NULL CHECK (char_length(trim(title)) BETWEEN 1 AND 30),
            body varchar(300) NOT NULL CHECK (char_length(trim(body)) BETWEEN 1 AND 300),
            status text NOT NULL DEFAULT 'active'
                CHECK (status IN ('active','expired','hidden')),
            version integer NOT NULL DEFAULT 1 CHECK (version > 0),
            created_at timestamptz NOT NULL DEFAULT now(),
            expires_at timestamptz NOT NULL DEFAULT now() + interval '72 hours',
            closed_at timestamptz,
            delete_after timestamptz,
            CHECK ((status='active' AND closed_at IS NULL)
                OR (status<>'active' AND closed_at IS NOT NULL))
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_looking_posts_feed_new ON discovery.looking_posts(city_id, created_at DESC, id DESC) WHERE status='active'"
    )
    op.execute(
        """
        CREATE TABLE discovery.looking_post_likes (
            looking_post_id uuid NOT NULL REFERENCES discovery.looking_posts(id) ON DELETE CASCADE,
            user_id uuid NOT NULL,
            active boolean NOT NULL DEFAULT true,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (looking_post_id, user_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_looking_post_likes_active ON discovery.looking_post_likes(looking_post_id) WHERE active"
    )
    op.execute(
        """
        CREATE TABLE discovery.looking_post_questions (
            id uuid PRIMARY KEY,
            looking_post_id uuid NOT NULL REFERENCES discovery.looking_posts(id) ON DELETE CASCADE,
            asker_user_id uuid NOT NULL,
            question varchar(200) NOT NULL CHECK (char_length(trim(question)) BETWEEN 1 AND 200),
            answer varchar(300),
            answered_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            delete_after timestamptz,
            CHECK ((answer IS NULL AND answered_at IS NULL) OR (answer IS NOT NULL AND answered_at IS NOT NULL))
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_looking_post_one_unanswered ON discovery.looking_post_questions(looking_post_id, asker_user_id) WHERE answer IS NULL"
    )
    op.execute(
        "CREATE INDEX ix_looking_post_questions_public ON discovery.looking_post_questions(looking_post_id, answered_at, id) WHERE answer IS NOT NULL"
    )
    op.execute(
        """
        CREATE TABLE discovery.looking_post_requests (
            user_id uuid NOT NULL,
            idempotency_key uuid NOT NULL,
            action varchar(16) NOT NULL CHECK (action IN ('create','question','answer')),
            request_fingerprint char(64) NOT NULL,
            resource_id uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (user_id, idempotency_key)
        )
        """
    )
    op.execute(
        "ALTER TABLE trust_safety.profile_reports ADD COLUMN source_question_id uuid, ADD COLUMN source_looking_post_id uuid"
    )
    op.execute(
        "ALTER TABLE trust_safety.profile_reports ADD CONSTRAINT ck_profile_report_source CHECK (source_question_id IS NULL OR source_looking_post_id IS NOT NULL)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE trust_safety.profile_reports DROP CONSTRAINT ck_profile_report_source")
    op.execute("ALTER TABLE trust_safety.profile_reports DROP COLUMN source_looking_post_id, DROP COLUMN source_question_id")
    op.execute("DROP TABLE discovery.looking_post_requests")
    op.execute("DROP TABLE discovery.looking_post_questions")
    op.execute("DROP TABLE discovery.looking_post_likes")
    op.execute("DROP TABLE discovery.looking_posts")
    op.execute("ALTER TABLE discovery.cities DROP COLUMN looking_posts_enabled")
