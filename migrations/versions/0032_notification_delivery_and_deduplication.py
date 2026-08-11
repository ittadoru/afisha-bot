"""Add notification delivery state and stable business keys."""

from collections.abc import Sequence

from alembic import op

revision: str = "0032_notification_delivery_and_deduplication"
down_revision: str | None = "0031_profile_backgrounds"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE communication.notifications
          ADD COLUMN business_key varchar(180),
          ADD COLUMN delivery_policy text NOT NULL DEFAULT 'telegram_and_in_app'
            CHECK (delivery_policy IN ('in_app_only', 'telegram_and_in_app')),
          ADD COLUMN telegram_status text NOT NULL DEFAULT 'pending'
            CHECK (telegram_status IN ('pending', 'sent', 'unreachable')),
          ADD COLUMN telegram_last_attempt_at timestamptz,
          ADD COLUMN telegram_sent_at timestamptz;
        CREATE UNIQUE INDEX uq_notifications_business_key
          ON communication.notifications(business_key)
          WHERE business_key IS NOT NULL;
        CREATE INDEX ix_notifications_feed
          ON communication.notifications(recipient_user_id, created_at DESC, id DESC);
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX communication.ix_notifications_feed")
    op.execute("DROP INDEX communication.uq_notifications_business_key")
    op.execute(
        """
        ALTER TABLE communication.notifications
          DROP COLUMN telegram_sent_at,
          DROP COLUMN telegram_last_attempt_at,
          DROP COLUMN telegram_status,
          DROP COLUMN delivery_policy,
          DROP COLUMN business_key;
        """
    )
