"""Event chat state, message idempotency and Telegram delivery marker."""

from collections.abc import Sequence

from alembic import op

revision: str = "0029_event_chat_and_telegram"
down_revision: str | None = "0028_manual_event_address_parts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE events.events "
        "ADD COLUMN chat_enabled boolean NOT NULL DEFAULT true"
    )
    op.execute(
        """
        CREATE TABLE communication.chat_message_requests (
            user_id uuid NOT NULL,
            idempotency_key uuid NOT NULL,
            request_fingerprint char(64) NOT NULL,
            message_id uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (user_id, idempotency_key)
        )
        """
    )
    op.execute(
        "ALTER TABLE communication.notifications ADD COLUMN tg_pushed_at timestamptz"
    )
    op.execute(
        "CREATE INDEX ix_notifications_tg_pending "
        "ON communication.notifications(tg_pushed_at) "
        "WHERE tg_pushed_at IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX communication.ix_notifications_tg_pending")
    op.execute("ALTER TABLE communication.notifications DROP COLUMN tg_pushed_at")
    op.execute("DROP TABLE communication.chat_message_requests")
    op.execute("ALTER TABLE events.events DROP COLUMN chat_enabled")
