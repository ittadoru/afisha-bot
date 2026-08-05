"""Add staff identities, sessions, permissions, throttling and audit."""

from collections.abc import Sequence

from alembic import op

revision: str = "0018_staff_admin_foundation"
down_revision: str | None = "0017_profiles_and_reports"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE trust_safety.staff_accounts (
            id uuid PRIMARY KEY,
            login varchar(64) NOT NULL,
            role text NOT NULL CHECK (role IN ('admin', 'moderator')),
            status text NOT NULL DEFAULT 'active'
                CHECK (status IN ('active', 'disabled')),
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE UNIQUE INDEX uq_staff_accounts_login_ci
            ON trust_safety.staff_accounts (lower(login));

        CREATE TABLE trust_safety.staff_credentials (
            staff_id uuid PRIMARY KEY REFERENCES trust_safety.staff_accounts(id)
                ON DELETE CASCADE,
            password_hash text NOT NULL,
            version integer NOT NULL DEFAULT 1 CHECK (version > 0),
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        );

        CREATE TABLE trust_safety.staff_sessions (
            id uuid PRIMARY KEY,
            staff_id uuid NOT NULL REFERENCES trust_safety.staff_accounts(id)
                ON DELETE CASCADE,
            token_hash bytea NOT NULL UNIQUE,
            csrf_token_hash bytea NOT NULL,
            expires_at timestamptz NOT NULL,
            last_seen_at timestamptz NOT NULL DEFAULT now(),
            revoked_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            CHECK (expires_at > created_at)
        );
        CREATE INDEX ix_staff_sessions_staff_id
            ON trust_safety.staff_sessions(staff_id);

        CREATE TABLE trust_safety.staff_login_limits (
            login_digest bytea NOT NULL,
            source_digest bytea NOT NULL,
            failed_attempts smallint NOT NULL DEFAULT 0 CHECK (failed_attempts >= 0),
            first_failed_at timestamptz NOT NULL DEFAULT now(),
            blocked_until timestamptz,
            updated_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (login_digest, source_digest)
        );

        CREATE TABLE trust_safety.staff_permissions (
            staff_id uuid NOT NULL REFERENCES trust_safety.staff_accounts(id)
                ON DELETE CASCADE,
            permission varchar(100) NOT NULL,
            granted_by_staff_id uuid REFERENCES trust_safety.staff_accounts(id),
            granted_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (staff_id, permission)
        );

        CREATE TABLE trust_safety.staff_audit_log (
            id uuid PRIMARY KEY,
            actor_staff_id uuid REFERENCES trust_safety.staff_accounts(id),
            action varchar(100) NOT NULL,
            result text NOT NULL CHECK (result IN ('success', 'failure', 'blocked')),
            source_digest bytea,
            details jsonb NOT NULL DEFAULT '{}'::jsonb,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_staff_audit_log_created_at
            ON trust_safety.staff_audit_log(created_at DESC);

        CREATE FUNCTION trust_safety.reject_staff_audit_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'staff audit records are immutable';
        END;
        $$;
        CREATE TRIGGER staff_audit_immutable
            BEFORE UPDATE OR DELETE ON trust_safety.staff_audit_log
            FOR EACH ROW EXECUTE FUNCTION trust_safety.reject_staff_audit_mutation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER staff_audit_immutable ON trust_safety.staff_audit_log")
    op.execute("DROP FUNCTION trust_safety.reject_staff_audit_mutation")
    op.execute("DROP TABLE trust_safety.staff_audit_log")
    op.execute("DROP TABLE trust_safety.staff_permissions")
    op.execute("DROP TABLE trust_safety.staff_login_limits")
    op.execute("DROP TABLE trust_safety.staff_sessions")
    op.execute("DROP TABLE trust_safety.staff_credentials")
    op.execute("DROP TABLE trust_safety.staff_accounts")
